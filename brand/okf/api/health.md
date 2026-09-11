---
type: API Endpoint
title: Health
description: Actuator health endpoint; the only machine-readable signal that the service can reach its database.
resource: http://localhost:8080/actuator/health
tags: [api, ops]
generated: { by: claude-code/opus-5, at: 2026-09-09T09:30:00Z }
status: draft
---

# Operations

| Method | Path | Returns |
|---|---|---|
| `GET` | `/actuator/health` | `200 {"status":"UP"}`, or `503 {"status":"DOWN"}` when the database is unreachable |

Only `health` is exposed over HTTP — `/actuator/env`, `/actuator/beans` and the rest return
`404`. Details are suppressed, so the body carries a status and nothing about the host.

# Authentication

**None.** `/actuator/health` and `/actuator/health/**` are on
`SecurityConfig.ANONYMOUS_PATHS`, because a probe that needs a credential is a probe that
reports `401` as an outage. A probe that happens to carry a credential is covered too: an
anonymous route ignores the `Authorization` header entirely, so a probe still holding an
expired or revoked token answers `200` rather than reporting an outage that is not one.
Nothing is leaked by it: details are suppressed, so the body is a status word. The rest of `/actuator/**` is not exempt, and is not exposed over HTTP
either.

# Why it exists

The application starts and serves traffic even when PostgreSQL is unreachable: the
connection pool is lazy, so the failure appears only on the first query, as a `500`
indistinguishable from any other. Without this endpoint nothing outside the process can
tell a healthy instance from one failing every request.

# Readiness is deliberately not database-aware

`/actuator/health/readiness` returns `200 UP` while the database is down — the readiness
group carries only the application's own lifecycle state. This is the framework's
recommendation, not an oversight: a readiness probe that depends on a shared database
removes **every** instance from the load balancer during one database outage, converting a
degraded service into a total one.

So: wire alerting to `/actuator/health`, which is database-aware. Do not wire a Kubernetes
readiness probe to it, and do not assume `/actuator/health/readiness` says anything about
the database.
