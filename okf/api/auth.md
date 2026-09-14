---
type: API Endpoint
title: /api/auth
description: Exchanges a username and password for a bearer JWT; the only way to obtain a token for the rest of the API.
resource: http://localhost:8080/api/auth/login
tags: [api, auth]
generated: { by: claude-code/opus-5, at: 2026-09-11T07:02:03Z }
status: draft
---

# Operations

| Method | Path | Body | Success | Notes |
|---|---|---|---|---|
| `POST` | `/api/auth/login` | `{ "username": "...", "password": "..." }` | `200` | `{ "token": "eyJ…", "expiresAt": "2026-09-08T05:20:00Z" }` |

`400` when either field is missing or blank. `401` for a wrong password **and** for a
username that does not exist — the two are deliberately indistinguishable, in body and in
timing: `AuthService` runs a BCrypt comparison against a throwaway hash when the row is
absent, so response time does not reveal which usernames are real.

Errors are RFC 9457 problem documents like the rest of the API.

# The token

Signed HS256 with the key described under [Signing key](#signing-key). Claims are `sub`
(the `username` from [users](../tables/users.md)), `iat` and `exp` — nothing else.

**The role is deliberately not a claim.** `ADMIN` versus `USER` is read from the `users`
row on each call that needs it, so a promotion or demotion applies to the caller's next
request instead of whenever their current token happens to expire. A role in the token
would be a cached copy of a security decision, stale by up to an hour.

Lifetime is **one hour**, fixed in `AuthService.TOKEN_TTL`. `expiresAt` in the response is
the `exp` claim, truncated to whole seconds, which is the precision the claim actually
carries.

**There is no refresh token**: a client re-posts the credentials when the token expires.

**Revocation does exist**, and it is the one thing here that is not stateless. Every
authenticated request loads the account by `sub` and refuses the token when the account is
gone or when `password_changed_at` is later than the token's `iat`. So deleting an account
or changing its password strands the outstanding tokens at once, rather than an hour later.

Two consequences worth knowing. It costs **at least two `users` reads per authenticated
account request** — the decoder's check loads the row and discards it, then the service
loads the same row again to authorize, and an admin reaching another account by id pays a
third. Only the decoder's read is unavoidable; the rest is the price of the two layers not
sharing a loaded row, and collapsing it would mean a request-scoped cache. On endpoints
that never touch the principal, such as [`/api/samples`](samples.md), it is one read —
that is what buys revocation on a token that carries its own authority. And the comparison
keeps the cutoff's full precision against a whole-second `iat`, which closes rather than
opens the sub-second ambiguity: a token issued **earlier in the same second** as a password
change is refused. Flooring the cutoff to match `iat` would let exactly that token through
for its remaining hour.

Biasing it closed would ordinarily strand the caller who just changed their password and
logged straight back in, since `iat` is a second coarser than the cutoff. It does not,
because **login never issues a token its own account would refuse**: when the truncated
`iat` falls before the account's cutoff, it is rounded up to the first whole second past it.
An `iat` can therefore sit up to a second ahead of the real issue time, which nothing
validates. Both halves are pinned by `AuthServiceTest` —
`aTokenFromTheSameSecondAsTheChangeIsStale` and
`aLoginRightAfterAPasswordChangeIssuesAUsableToken`.

`iat` is read from the **database** clock, not the application's, because
`password_changed_at` is stamped by Postgres and the two are compared. Two clocks would
mean any skew between the app host and the database either strands fresh tokens or lets
revoked ones outlive the change.

It is read **before** the account row, not after it. The row is where the cutoff comes from,
and a password change committing between the two reads is invisible to the login either way
— but the order decides which way that falls. Reading the clock last dates the token after a
cutoff this login never saw, and the staleness check then waves it through for the full hour:
an attacker holding the old password, spraying logins across the moment the real owner
changes it, keeps a working token. Reading it first closes both branches — a change landing
before the row read is simply the wrong password now, and one landing after leaves `iat`
earlier than the new cutoff, so the token dies on first use and the caller logs in again.

The check is an `OAuth2TokenValidator<Jwt>` on the `JwtDecoder` bean in `SecurityConfig`,
delegating to `AuthService.isTokenStale`. Sitting on the decoder rather than in a filter is
what makes it apply everywhere a bearer token is read, `/api/samples` included. The rule is
covered by `AuthServiceTest`; that it is actually wired to the decoder is covered by
`SecurityConfigTest`, which uses a token belonging to a deleted account.

# Signing key

From the `JWT_SECRET` environment variable (`jwt.secret` in `application.yaml`), which must
be at least 32 bytes — HS256 rejects less, and `SecurityConfig` fails startup with that
message rather than at the first login. An untracked `brand/.env` supplies
it locally: `application.yaml` imports that file with `optional:file:.env[.properties]`, so
a real environment variable and a `.env` line reach the same property, and a checkout
without the file boots unchanged.

**When it is unset, a random key is generated at startup** and a `WARN` is logged. That
keeps a developer booting without ceremony, at the price of every token dying with the
process and no two instances agreeing on one. A default secret committed to this
repository would sign production tokens for anyone who cloned it, which is why there is
none.

# Authentication

`POST /api/auth/login` is itself anonymous — it is how a token is obtained. It is one of
the paths in `SecurityConfig.ANONYMOUS_PATHS`; everything not on that list requires a
bearer token, with one method-scoped exception for signup ([/api/users](users.md)).

An anonymous route also **ignores any `Authorization` header it is sent**. That is not
cosmetic: `BearerTokenAuthenticationFilter` runs before the authorization rules, so a
request carrying a header is decided by the token before `permitAll` is consulted. Without
the exemption, a client whose token was just stranded by its own password change would get
`401` from this endpoint — the one route that could hand it a working token — and could not
recover without knowing to strip the header. The exemption is scoped to anonymous routes;
an authenticated route still refuses an unusable token rather than falling through to
anonymous access. `SecurityConfig.ANONYMOUS` is the single matcher behind both the
authorization rules and the token resolver, so the two cannot drift.

Since signup is open to anyone, a token is proof of *identity*, not of admission: see
[/api/users](users.md#authentication) for what that does and does not buy.

**A browser on another origin reaches this endpoint only if its origin is listed.**
`CORS_ALLOWED_ORIGINS` — comma-separated, exact scheme, host and port — is that list, and
`SecurityConfig` applies it to `/api/**`. Unset, no mapping is registered: a cross-origin
response carries no `Access-Control-*` header and the browser discards it, which is how
this API behaved before the list existed. An origin that is not on it gets `403` on the
preflight and never sends the real request.

The list is the only limit on this endpoint from a browser. Login is anonymous and nothing
rate-limits it, so a wildcard would let any web page run password guesses through its own
visitors' browsers — which is why the entries are exact origins and why
`allowedOriginPatterns`, the wildcard-subdomain form, is deliberately not used. Credentials
are off: the token rides the `Authorization` header, so no cookie crosses origins and the
reason CSRF is disabled elsewhere still holds.

CORS is configured in the **security filter chain**, rather than a `WebMvcConfigurer`,
so its `CorsFilter` handles preflight before authorization. A preflight `OPTIONS` carries
no bearer token; authorizing it first would return `401` before the browser sends the real
request. Allowed methods are explicit: `applyPermitDefaultValues()` only includes `GET`,
`HEAD` and `POST`, leaving `PUT` and `DELETE` preflights unsupported.

CSRF is disabled and sessions are `STATELESS`: the token travels in an `Authorization`
header a cross-site form cannot set, and there is no session cookie for it to use.
Enabling CORS credentials would require reconsidering that policy.

None of this reaches a server-to-server caller. CORS is a browser rule — no `Origin` header
means no CORS processing and no preflight, so a backend calling this endpoint is unaffected
whether or not the list is set.

# Shape

`AuthController` → `AuthService` → `UserMapper` + `mapper/UserMapper.xml`, all under
`com.eland.brand.auth`. The request body binds to the `User` POJO: `password` is
write-only and `passwordHash` is `@JsonIgnore`, so neither the stored hash nor the
submitted plaintext can be echoed back by a future change that serializes a `User`.

`AuthService` covers login, the account rules of [/api/users](users.md) and the staleness
check, all under `AuthServiceTest`; the filter-chain rules it depends on are covered by
`SecurityConfigTest`, the documented exception to the service-layer-only testing policy in
[CLAUDE.md](../../brand/CLAUDE.md).
