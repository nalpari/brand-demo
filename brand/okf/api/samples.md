---
type: API Endpoint
title: /api/samples
description: CRUD over the sample table, exposed by SampleController.
resource: http://localhost:8080/api/samples
tags: [api, sample]
generated: { by: claude-code/opus-5, at: 2026-09-11T01:06:00Z }
status: draft
---

# Operations

| Method | Path | Body | Success | Notes |
|---|---|---|---|---|
| `GET` | `/api/samples` | — | `200` list | Ordered by `id`, 50 rows per page. `?afterId=` is the last `id` of the previous page and defaults to `0`; any value is accepted, including one past the end, which returns `[]`. |
| `GET` | `/api/samples/{id}` | — | `200` / `404` | |
| `POST` | `/api/samples` | `{ "name": "..." }` | `201` | Returns the row including database-assigned `id` and `created_at`. |
| `PUT` | `/api/samples/{id}` | `{ "name": "..." }` | `200` / `404` | Replaces `name` only. |
| `DELETE` | `/api/samples/{id}` | — | `204` / `404` | |

`id` and `createdAt` are read-only: the OpenAPI schema marks them so, and a client that
sends them anyway is ignored rather than rejected. `name` is the only writable field.

The page size is fixed at 50 and the response is a bare array — there is no envelope, so the
cursor is the last `id` of the page and a caller walks the table by feeding it back as
`?afterId=`. A page shorter than 50 is the last one. Paging exists so that one request cannot
materialize the whole table in heap — a cap that matters even now that the endpoint is
authenticated, since every account can call it.

It is keyset (`where id > ?`), not `limit/offset`, and that is a correctness choice, not a
performance one: this API also deletes, and under `OFFSET` a row deleted behind the cursor
pulls the later rows back by one, so a paging client silently never sees one. Keyset also
makes a far-off `afterId` an index seek instead of a scan through everything before it.

Errors are RFC 9457 problem documents (`spring.mvc.problemdetails.enabled`), so the reason
reaches the caller — `{"detail": "name is required", "status": 400, ...}`. A `name` returns
`400` when it is missing, when it carries no visible character (whitespace, `U+00A0`,
`U+200B` and other separator or format code points all count as blank), when it contains a
NUL character, or when it exceeds 20 code points. The NUL check exists because PostgreSQL
rejects the byte and the failure would otherwise surface as a `500`; the length cap exists
because `name` is an unbounded `text` column.

A body over 8KB is refused with `400` and `{"detail": "Failed to read request"}` before any
field is bound, so the 20-code-point rule above only ever runs on a body already known to be
small. The cap is a Jackson `maxDocumentLength` set in `BrandApplication`, not a
`Content-Length` filter, which means a chunked request carrying no length is held to it too.
It is not decoration: Jackson defaults to an unlimited document and a 100M-character string,
so without it one `POST` can spend roughly 200MB of heap on a single `name` before the
service sees it. This is the one API rule with no test — it is not service-layer logic,
so the testing policy in [CLAUDE.md](../../CLAUDE.md) has nowhere to put it; it was checked
by hand over HTTP instead, chunked and unchunked.

# Authentication

**All five operations require a bearer token.** `SecurityConfig` authenticates every
request except the paths in its `ANONYMOUS_PATHS` list, and `/api/samples` is not one of
them: a call without `Authorization: Bearer <jwt>` gets `401`, as does one with a token
that is expired, malformed, or signed with another key.

Get a token from [`POST /api/auth/login`](auth.md), then:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/samples
```

The identity is available but unused: no operation here reads the principal, so every
authenticated caller sees and edits the same rows. `sample` has no owner column and this
API applies no per-user rule — authentication says *someone valid* is calling, not *who
may touch what*.

From a browser on another origin the token is not enough by itself: the caller's origin has
to be in `CORS_ALLOWED_ORIGINS`, which `SecurityConfig` applies to `/api/**` — see
[`/api/auth/login`](auth.md#authentication). The two gates are independent. CORS decides
whether the browser may make the call at all; the token decides whether the server answers
it, and a listed origin with no token still gets `401`. `PUT` and `DELETE` are on the
allowed-method list explicitly rather than by default — Spring's permit-defaults cover
`GET`, `HEAD` and `POST` only, which would have failed preflight on exactly those two while
every read kept working.

And since [signup is anonymous](users.md), anyone willing to `POST /api/users` first can
become such a caller. The `401` is therefore a speed bump and an attribution mechanism, not
an access barrier: what it buys is that every call belongs to a named account which can be
deleted, stranding its tokens at once. Do not treat these five operations as protected
data.

CSRF is disabled. That is correct rather than leftover: the token travels in a header a
cross-site form cannot set, and `SessionCreationPolicy.STATELESS` means there is no
session cookie for such a request to ride.

# Shape

The controller serializes the [sample table](../tables/sample.md) row directly —
there is no DTO layer, so a column added to the table appears in the API
response.

Layers: `SampleController` → `SampleService` → `SampleMapper` +
`mapper/SampleMapper.xml`, all under `com.eland.brand.sample`.
