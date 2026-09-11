# brand

E-Land brand service. Spring Boot 4 + MyBatis + PostgreSQL.

## Prerequisites

- **JDK 17.** The Gradle toolchain is pinned to 17 in `build.gradle`; the build fails
  outright on a machine that only has a newer JDK, rather than falling back to it.
- **Docker**, for PostgreSQL.

## Getting started

```bash
# 1. PostgreSQL
docker run -d --name pg -p 5432:5432 \
  -e POSTGRES_DB=appdb -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app \
  -v pgdata:/var/lib/postgresql postgres:18-alpine

# 2. Create the tables — there is no migration tool, see below
docker exec -i -e PGPASSWORD=app pg psql -U app -d appdb <<'SQL'
create table sample (
  id         bigserial primary key,
  name       text not null,
  created_at timestamptz not null default now()
);
SQL

# 3. Run
./gradlew bootRun
```

Then open **http://localhost:8080/swagger-ui.html**. The UI loads without a login, and so
does `POST /api/users`; every `/api/samples` call returns `401` until you sign up, log in
and paste the bearer token — see [Security](#security).

Credentials live in `src/main/resources/application.yaml` and are the container's
defaults — fine locally, not fine anywhere else.

## Running

```bash
./gradlew bootRun                                # development, Ctrl+C to stop
./gradlew bootRun --args='--server.port=9090'    # different port

./gradlew bootJar                                # package
java -jar build/libs/brand-0.0.1-SNAPSHOT.jar    # run the packaged app
```

Port 8080 by default.

The app starts whether or not the database is reachable — the connection pool is lazy, so a
dead database is not a startup error. It surfaces on the first request that touches it:
Swagger UI still loads, `GET /api/samples` returns `500`. `GET /actuator/health` is the
signal that tells the two apart: `503 {"status":"DOWN"}` means the database, not the code
([details](okf/api/health.md)).

## Tests

```bash
./gradlew test                                                     # all
./gradlew test --tests 'com.eland.brand.sample.SampleServiceTest'  # one class
./gradlew test --tests '*SampleServiceTest.createRejectsBlankName' # one method
```

**Tests need the database running.** There is no embedded/in-memory database on the
classpath: every test boots a Spring context against the real `spring.datasource.url`.
Rows written by tests roll back (`@Transactional`), so the database is left as it was.

Tests are written test-first and live on service classes only — one `SampleServiceTest`
per domain, no mapper or controller tests. That is a deliberate policy, spelled out with
its reasoning in [CLAUDE.md](CLAUDE.md#testing-tdd-service-layer-only). Its practical
consequence: **logic that needs a test belongs in the service**, not the controller.

## Layout

```
src/main/java/com/eland/brand/
  BrandApplication.java     entry point
  SecurityConfig.java       filter chain, JWT keys, password encoder; see below
  auth/                     accounts and tokens: User → UserMapper → AuthService
                            → AuthController (login) + UserController (/api/users)
  sample/                   Sample → SampleMapper → SampleService → SampleController
src/main/resources/
  application.yaml          datasource + MyBatis settings + jwt.secret
  mapper/SampleMapper.xml   SQL for SampleMapper
  mapper/UserMapper.xml     SQL for UserMapper
okf/                        knowledge bundle: tables and endpoints, see below
```

One package per domain under `com.eland.brand`; `sample/` is the reference implementation
to copy. SQL is not in annotations — mapper interfaces are empty and every statement lives
in `src/main/resources/mapper/<Name>Mapper.xml`, keyed by the interface's fully-qualified
name.

Domain classes are mutable POJOs rather than records: `useGeneratedKeys` writes the generated
key back into the object it was handed, which an immutable record cannot accept.

## Schema management: none

No Flyway, no Liquibase, no JPA `ddl-auto`. Tables are created by hand with `psql`, which
means **a schema change is not captured by pulling this repository**. The DDL of record
lives in [`okf/tables/`](okf/tables/index.md); when you add or alter a table, run the DDL
*and* update that document, or the next person will not know it happened.

## Security

Every request needs a bearer JWT except `POST /api/auth/login`, `POST /api/users`,
`/actuator/health`, `/v3/api-docs*` and `/swagger-ui*`. All but signup are in
`SecurityConfig.ANONYMOUS_PATHS`; signup is opened by method, because a path entry there
would open `GET`/`PUT`/`DELETE` on `/api/users` too. `SecurityConfigTest` checks both.

Signup is anonymous, so getting in takes no database step:

```bash
curl -X POST http://localhost:8080/api/users \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"correct-horse"}'

TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"correct-horse"}' | sed 's/.*"token":"\([^"]*\)".*/\1/')

curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/samples
```

An account manages itself at `/api/users/me` — `GET` to read it, `PUT` to change the
password (the current one is required), `DELETE` to remove it. An `ADMIN` may use a numeric
id in place of `me` to reach any account, or `GET /api/users?username=…` to find one by
name — that lookup answers for your own username and, to an `ADMIN`, for anyone's. **`role` cannot be set through the API**; promote
with `psql`:

```sql
update users set role = 'ADMIN' where username = 'alice';
```

Tokens are HS256, last one hour, and carry only `sub`/`iat`/`exp` — the role is read from
the database on each call, so a promotion applies immediately. There is no refresh token.
Changing a password or deleting an account **does** invalidate that account's outstanding
tokens at once, at the cost of one `users` read per authenticated request.

**Set `JWT_SECRET`** (32+ bytes) anywhere the process outlives one boot. Unset, the
application generates a random key at startup and logs a `WARN` — tokens then die with the
process and no two instances agree on one. There is deliberately no default secret in this
repository.

Locally, put it in an untracked `.env` at the repository root, which `application.yaml`
imports optionally:

```bash
printf 'JWT_SECRET=%s\n' "$(openssl rand -base64 32)" > .env
```

`.env` is git-ignored. A real environment variable works the same way and wins where both
are set.

**Set `CORS_ALLOWED_ORIGINS`** to let a browser on another origin call `/api/**` — a
comma-separated list of exact origins, scheme, host and port included
(`https://app.example.com,https://admin.example.com`). Unset, nothing is registered and a
cross-origin response carries no `Access-Control-*` header, so the browser discards it; an
origin that is not on the list gets `403` on the preflight. Wildcard subdomains are not
supported on purpose — one weak host under the domain would open the API. It goes in the
same `.env`, and it changes nothing for a server-to-server caller, which sends no `Origin`
and never triggers a preflight.

**Because signup is anonymous, authentication is not a barrier to `/api/samples`** — anyone
may create an account and call it. What it buys is identity: every call belongs to an
account, and deleting that account strands its tokens immediately. The `sample` rows
themselves have no owner and no per-user rule; `role` governs access to *accounts* only.
See [`okf/api/users.md`](okf/api/users.md) and [`okf/api/auth.md`](okf/api/auth.md).

## Documentation

- [`okf/`](okf/index.md) — an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
  bundle: plain markdown describing the [tables](okf/tables/index.md) and the
  [endpoints](okf/api/index.md). This, not the README, is the reference for what a column
  or an endpoint means, and it is expected to be updated alongside the code that changes.
- [`CLAUDE.md`](CLAUDE.md) — conventions and traps, written for coding agents but accurate
  for humans: the Spring Boot 4 package moves that break builds, the MyBatis rules above,
  and the testing policy.
- `http://localhost:8080/v3/api-docs` — OpenAPI 3.1 document, generated from the
  controllers at runtime.
- `http://localhost:8080/actuator/health` — the only endpoint that reports whether the
  service can reach its database.
