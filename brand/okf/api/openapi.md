---
type: API Endpoint
title: OpenAPI / Swagger UI
description: Machine-readable API spec and its browser UI, generated at runtime by springdoc.
resource: http://localhost:8080/swagger-ui.html
tags: [api, tooling]
generated: { by: claude-code/opus-5, at: 2026-09-09T09:30:00Z }
status: draft
---

# Operations

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v3/api-docs` | OpenAPI 3.1.0 document, JSON |
| `GET` | `/swagger-ui.html` | Redirects to `/swagger-ui/index.html` |

Paths, verbs and schemas are not hand-written: `springdoc-openapi-starter-webmvc-ui` reads
the controllers at startup, and a new `@RestController` appears here with no further work.

Two things are declared by hand, both about security. `SecurityConfig.openApi()` publishes
the `bearer-jwt` scheme and applies it to every operation — that bean is what puts the
**Authorize** button in the UI. The two anonymous `POST`s carry `@SecurityRequirements`
(empty) to clear it again; those annotations exist solely to feed this document, and they
are the only ones in the project that do.

# Authentication

**None for these two paths.** `/v3/api-docs`, `/v3/api-docs/**`, `/swagger-ui.html` and
`/swagger-ui/**` are on `SecurityConfig.ANONYMOUS_PATHS`, so the spec and the UI still load
without a token — the exemption exists precisely because losing it would make the docs
unreachable to anyone who has not already authenticated somewhere else. They load even
while the browser is holding a token the server no longer accepts, because an anonymous
route ignores the `Authorization` header rather than validating it.

The endpoints the UI *describes* are mostly not exempt. `POST /api/users` and
`POST /api/auth/login` work anonymously from "Try it out" — they show no padlock — which is
enough to sign up and get a token. Everything else returns `401` until that token is pasted
into the **Authorize** dialog, after which the UI attaches
`Authorization: Bearer <token>` to those operations; paste the token alone, without the
`Bearer ` prefix, which the scheme adds. `SecurityConfigTest` covers the exemptions
themselves.

The padlocks are a description, not the rule. If `ANONYMOUS_PATHS` and
`SecurityConfig.openApi()` ever disagree, the filter chain wins and this UI lies — which is
why the scheme is declared in that same file.

# Disabling

Both endpoints are on by default and springdoc warns about it at startup. Turn them off with
`springdoc.api-docs.enabled=false` and `springdoc.swagger-ui.enabled=false`.
