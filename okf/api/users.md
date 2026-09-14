---
type: API Endpoint
title: /api/users
description: Anonymous signup, plus self-service read, lookup, password change and deletion of an account; admins reach any account.
resource: http://localhost:8080/api/users
tags: [api, auth, users]
generated: { by: claude-code/opus-5, at: 2026-09-11T03:58:16Z }
status: draft
---

# Operations

| Method | Path | Body | Success | Who |
|---|---|---|---|---|
| `POST` | `/api/users` | `{ "username": "...", "password": "..." }` | `201` | **Anyone, no token** |
| `GET` | `/api/users?username=…` | — | `200` | Your own username, or an `ADMIN` |
| `GET` | `/api/users/{id}` | — | `200` | The account itself, or an `ADMIN` |
| `PUT` | `/api/users/{id}` | `{ "currentPassword": "...", "newPassword": "..." }` | `204` | The account itself, or an `ADMIN` |
| `DELETE` | `/api/users/{id}` | — | `204` | The account itself, or an `ADMIN` |

An account comes back as five fields, alphabetically ordered by Jackson:[^probe]

```json
{"createdAt":"2026-09-08T08:39:18.817595Z","id":1856,"passwordChangedAt":"2026-09-08T08:39:18.817595Z","role":"USER","username":"shape-probe"}
```

The timestamps are UTC with microsecond precision — Postgres `timestamptz` read as
`OffsetDateTime`, so they carry the column's full resolution and not the whole seconds the
token's `iat` compares. Every field is `READ_ONLY`, so sending this same shape back in a
request body sets nothing. `password` is `WRITE_ONLY` and `passwordHash` is `@JsonIgnore`d,
so neither ever appears; see [users](../tables/users.md) for what the columns mean. `PUT`
and `DELETE` return `204` with no body.

[^probe]: Captured from a running instance on 2026-09-08.

`{id}` accepts the literal **`me`** as well as a numeric id. A client that has just logged
in knows its `username` from the token's `sub` and not its `id`, so `me` is the normal form
and a number is what an admin uses to reach somebody else.

`GET /api/users?username=…` looks one account up by name. It is **not** a list: the
parameter is required and a missing one is `400`, never every row. There is deliberately no
listing at all, because handing out every username is the account enumeration that
[`/api/auth/login`](auth.md) spends a wasted BCrypt round per failed login to prevent.

The lookup is restricted for the same reason, and the restriction is what makes it safe to
have: signup is anonymous, so one request buys the token to probe with, and an endpoint
that told any caller whether a username exists would undo the login defence one name at a
time. So a plain caller may ask only about **their own** username and gets `403` for every
other name — the same `403` whether the name exists or not. Only an `ADMIN` sees `404`,
and an admin can already open any account by id, so this is a second key to a door they
hold rather than a new door.

That restriction narrows the enumeration surface; it does not close it. `POST /api/users`
is anonymous and answers `409` for a name already taken, so one unauthenticated request per
name still tells a caller whether that name exists — a cheaper oracle than the one the
`403` shuts. This is the usual price of open signup and is accepted deliberately, but the
`403` above should be read as reducing the rate at which names leak, not as a guarantee
that they do not.

# Status codes

| Code | When |
|---|---|
| `400` | A username that is empty once invisible characters are removed or that contains a NUL, a username over 50 characters, a password under 8 characters or over 72 bytes, a missing `?username=`, or an `{id}` that is neither a number nor `me` |
| `401` | No token, a revoked one, or — on `PUT` against your own account — a wrong `currentPassword` |
| `403` | A `USER` naming another account's id or username. Returned **without looking the row up**, so it reveals nothing about whether that account exists |
| `404` | Only an `ADMIN` sees this, for an id or username that is not there — and on `DELETE` when the row was removed between the authorization check and the write, so a write that touched no row is never reported as success |
| `409` | `username` already taken; and on `PUT` when the account moved under the write — the row was deleted, or another password change committed while this one was hashing |

A username is **trimmed** before it is stored or looked up, and rejected if what remains is
empty once whitespace and other invisible code points are removed, or if it contains a NUL.
`users_username_key` is a plain btree on `text`, so `" alice"` stored untrimmed would be a
second account rendering identically to `alice` everywhere a name is shown; trimming turns
that into the `409` it should be. The NUL guard is what keeps an anonymous caller from
turning a value Postgres refuses in a text parameter into a `500`. Case is **not** folded:
`Alice` and `alice` remain distinct accounts, which would need a case-insensitive unique
index to change.

`PUT` writes only while the row still holds the hash the `currentPassword` check ran
against. It reads the row, spends two BCrypt rounds on it, and then updates — so a second
change can commit in between, and a bare `where id` update would overwrite it with a
password proved against a hash that is no longer current. That is a takeover the losing
caller should not win: it would also re-stamp `password_changed_at` and strand the tokens
the winning change had just issued. The update carries the expected hash in its predicate,
so the loser touches no row and gets `409` instead of a silent `204`. Retrying re-reads the
account and either succeeds or reports the wrong `currentPassword` honestly.
`AuthServiceTest.aPasswordChangeThatVerifiedAHashTheRowNoLongerHasIsRefused` pins it.

The 72-byte password cap is not arbitrary: BCrypt hashes the first 72 bytes and drops the
rest silently, so a longer password would be accepted, truncated, and quietly weaker than
the user believes.

# role cannot be granted through this API

Signup is anonymous, so a request body able to set `role` would be an anonymous route to an
administrator account. `User.role` is `READ_ONLY` in JSON and `AuthService.signup` never
reads a role at all — it inserts and lets the column default to `USER`. Promotion is a
`psql` update; see [users](../tables/users.md).

`SecurityConfigTest` posts `{"role":"ADMIN"}` at signup and asserts the created account
comes back `USER`.

# Revocation

Changing a password or deleting an account **invalidates every token issued before it**,
across the whole API and not just these paths. The check lives in an
`OAuth2TokenValidator` attached to the `JwtDecoder` in `SecurityConfig`, so it runs
wherever a bearer token is verified.

For the revocation query cost, timestamp precision, and issuance after a password change,
see [/api/auth — The token](auth.md#the-token).

# Authentication

`POST /api/users` is anonymous. It is opened **by method**, not by adding `/api/users` to
`SecurityConfig.ANONYMOUS_PATHS` — a path entry there matches every verb and would have
handed the rest of this resource to anonymous callers, `GET /api/users?username=…`
included, which shares its path with the permitted `POST` exactly. `SecurityConfigTest`
asserts that same-path `GET` answers `401` without a token, along with the other verbs.

Being anonymous also means the `Authorization` header is ignored here, so signup works from
a client still holding a dead token — the same rule that keeps
[`/api/auth/login`](auth.md#authentication) reachable, and for the same reason.

Because signup is open, **authentication is not an access barrier for the rest of the
API**: anyone may create an account and reach [`/api/samples`](samples.md) with it. What it
still gives is identity — every call is attributable to an account, and one that misbehaves
can be deleted, which strands its tokens at once.

`/api/users` is under `/api/**`, so a **cross-origin** signup from a browser also needs the
caller's origin in `CORS_ALLOWED_ORIGINS` — see
[`/api/auth/login`](auth.md#authentication) for the list and why its entries are exact
origins. Anonymous and cross-origin are separate gates: clearing CORS still leaves signup
open to anyone, and an unlisted origin is what keeps an arbitrary web page from creating
accounts through its visitors.

# Shape

`UserController` → `AuthService` → `UserMapper` + `mapper/UserMapper.xml`, all under
`com.eland.brand.auth`; the account rules share a service with login because they share a
table and a domain. The controller only binds `@AuthenticationPrincipal Jwt` and passes
`sub` down — every decision, including who may reach which account, is in `AuthService`
where `AuthServiceTest` can reach it.
