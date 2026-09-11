# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
./gradlew test                                              # all tests
./gradlew test --tests 'com.eland.brand.sample.SampleServiceTest'      # one class
./gradlew test --tests '*SampleServiceTest.createRejectsBlankName'     # one method
./gradlew build        # compile + test + jar
./gradlew bootRun      # run the app
```

No linter/formatter is configured. Existing code is tab-indented (Spring Initializr default).

**Search with `rg` (ripgrep) when it is installed**, falling back to `grep -r` when it is
not — `command -v rg` settles which. It matters here because `rg` honors `.gitignore` and
so skips `build/` and `.gradle/` unprompted, while `grep -r` walks straight into the
compiled classes and buries the hit you wanted.

**Tests require a running Postgres.** There is no embedded DB on the classpath, so
every test boots a Spring context against the real `spring.datasource.url`
(`localhost:5432/appdb`, `app`/`app`). Local instance is a Docker container named `pg`:

```bash
docker exec -i -e PGPASSWORD=app pg psql -U app -d appdb -c '\dt'
```

**Toolchain is pinned to Java 17** (`build.gradle`). Gradle fails outright if no JDK 17
is installed, even when a newer JDK is present.

## Worktrees

**사용자가 명시적으로 요청할 때만 만든다.** 브랜치를 새로 파거나 기능 작업을 해달라는 요청은
평소대로 git으로 처리한다.

| 플랫폼 | 위치 |
| --- | --- |
| Windows | `C:\workspace\.worktrees\brand\<관광명소>` |
| macOS / Linux | `~/.worktrees/brand/<관광명소>` |

- **워크트리 디렉터리 이름은 세계 관광명소**, 소문자 kebab-case: `machu-picchu`, `santorini`, `angkor-wat`
- **브랜치 이름은 포켓몬**, 소문자: `snorlax`, `gengar`, `lapras`

워크트리 생성·진입·정리 전에 [워크트리 절차](okf/development/worktrees.md)를 읽는다.
추적하지 않는 설정 파일을 추가하면 같은 변경에서 그 문서의 복사 목록도 갱신한다.

## Testing: TDD, service layer only

API work is test-driven. Write the failing case in `<Domain>ServiceTest` first, run it and
watch it fail for the reason you expect, then write the code that passes it.

**Tests live on service classes and nowhere else** — one `<Domain>ServiceTest` per domain
package, no mapper tests, no controller tests. `BrandApplicationTests` (context smoke test)
and `SecurityConfigTest` below are the exceptions.

That policy has a consequence worth honoring: **logic that needs a test belongs in the
service.** A controller that validates input, maps errors, or decides anything is
untestable here, so keep controllers to routing and response shaping and push the decision
down into the service.

Service tests run against the real database — `@SpringBootTest` plus `@Transactional` so
rows roll back. Do not mock the mapper: the SQL in `mapper/*.xml` has no other coverage,
and a test with a mocked mapper asserts only that the service called a method.

**One documented exception: `SecurityConfigTest`.** The filter chain's path rules are not
reachable from a service — which path is open and which returns `401` is decided in
`SecurityConfig`, and no bean a service test can autowire answers it. So that one class
uses `@AutoConfigureMockMvc` and drives real requests. It is the only MockMvc test in the
repository, and the exception covers exactly the rules **no service bean can observe**: the
filter chain itself, the JSON serialization contract (`role` is ignored on the way in, the
hash never leaves), and the `JwtDecoder`'s revocation validator being wired at all. Nothing
that a service call can reach belongs here — per-account authorization lives in
`AuthService` and is tested like any other service logic. Adding or removing an anonymous
path *or method* means a case in it, or the change is untested.

## Schema management: none

No Flyway/Liquibase, no JPA `ddl-auto` (MyBatis only). Tables are created by hand with
`psql` and documented in [`okf/tables/`](okf/tables/index.md) — that bundle, not this file,
is the schema reference. Adding a table means running the DDL against the DB, writing its
`okf/tables/` doc, *and* telling the user; nothing in the repo will create or reconcile it.

## Knowledge bundle (`okf/`)

`okf/` is an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
v0.2 bundle: plain markdown + YAML frontmatter describing DB tables, REST endpoints,
and development procedures. It is documentation, not code — nothing builds or reads it at runtime.
Every non-`index.md` file needs a non-empty `type` in frontmatter; `index.md` carries
frontmatter only at the bundle root (`okf_version`).

**`okf/` is the reference; this file is the rules.** Anything the bundle already documents
— table columns, endpoint contracts, what a field means — belongs there and only there.
Link to it from here instead of restating it: CLAUDE.md is read in full every session, so
it stays short, and a fact that lives in one place cannot rot in the other. What belongs
here is what the bundle does not carry — commands, conventions, and traps that cost a build.

**When you change code, update the bundle in the same change.** Nothing builds, tests,
or lints `okf/`, so a stale bundle stays stale silently until someone trusts it and is
wrong. Concretely:

| You changed | Update |
|---|---|
| Table DDL, or what a column means | `okf/tables/<table>.md` — the schema table *and* the DDL block |
| A mapper's SQL, or which layer reads/writes a table | the `# Access` section of that table's doc |
| An endpoint's path, verb, request body, or status codes | `okf/api/<resource>.md` |
| The security configuration | the `# Authentication` section of every affected endpoint |
| Added a table or an endpoint | a new concept doc **and** the directory's `index.md` |

Refresh `generated.at` on any document you edit, and drop its `verified` entries — they
attested to content that no longer exists. If a code change leaves nothing in `okf/`
wrong, say so and move on; do not bump timestamps for their own sake.

## MyBatis conventions

- Mapper interface: `@Mapper`, no SQL annotations. SQL lives in
  `src/main/resources/mapper/<Name>Mapper.xml` with `namespace` = the interface's FQCN.
  `mybatis.mapper-locations: classpath:mapper/**/*.xml`.
- `type-aliases-package: com.eland.brand` — use the simple class name in `resultType`.
- `map-underscore-to-camel-case: true` — select raw snake_case columns, no aliases.
- **Always set `keyColumn` next to `keyProperty`.** Without it pgjdbc emits `RETURNING *`
  and MyBatis reads column *position 1*, so the key is bound by declaration order, not by
  name — correct only while the PK happens to be the first column declared. Verified on the
  wire: adding `keyColumn="id"` changes what Postgres receives to `RETURNING "id"`.
- **Domain classes are mutable POJOs, not records.** `useGeneratedKeys="true"` writes the
  generated id back into the parameter object, which an immutable record cannot accept.
  That is a constraint of `useGeneratedKeys`, not of MyBatis — a record can be built by
  constructor mapping from a `RETURNING` select — but that route needs a separate inbound
  type, which this project deliberately does not have.
- `@Mapper` interfaces are auto-scanned under the `@SpringBootApplication` package; there
  is no `@MapperScan`. Moving mappers outside `com.eland.brand` requires adding one.

## Security

**Bearer JWT; new endpoints require authentication by default.** Signup is permitted by
method (`POST /api/users`), never by opening every verb on that path.

**Do not add or remove an anonymous path or method, change the token's lifetime or claims,
touch CSRF and session policy, or add an origin to the CORS list without being asked.**
Adding an endpoint needs no security change.

**Signup is anonymous, so a token proves identity, not admission.** `/api/samples` has no
owner or per-user rule; do not describe it as protected or add data that assumes otherwise.

- **`role` is never settable through a request.** Keep `User.role` read-only in JSON.
- **Account authorization decisions live in `AuthService`, not controllers or the filter
  chain.** Test them in `AuthServiceTest`; the `SecurityConfigTest` exception is defined in
  [Testing](#testing-tdd-service-layer-only).
- **CORS belongs in the security filter chain, not a `WebMvcConfigurer`.** Explicitly list
  allowed methods; keep credentials off, CSRF disabled, and sessions `STATELESS`.

Before changing authentication or account behavior, read [auth](okf/api/auth.md) and
[users](okf/api/users.md). Token revocation and clock precision live in
[The token](okf/api/auth.md#the-token); CORS and CSRF rationale in
[Authentication](okf/api/auth.md#authentication). If tokens stop verifying after restart,
check `JWT_SECRET` against [Signing key](okf/api/auth.md#signing-key).

## Spring Boot 4 package/starter moves

Boot 4 split the monolithic starters and relocated test autoconfiguration. Reaching for the
Boot 3 names is the most common way to break the build here:

| Use | Not |
| --- | --- |
| `spring-boot-starter-webmvc`, `spring-boot-starter-webmvc-test` | `spring-boot-starter-web`, `spring-boot-starter-test` |

Test autoconfiguration moved too (`AutoConfigureTestDatabase` is now under
`org.springframework.boot.jdbc.test.autoconfigure`), but the testing policy above keeps this
project on plain `@SpringBootTest`, which needs none of it.

Boot 4 also serializes with **Jackson 3** (`tools.jackson.*`), not Jackson 2
(`com.fasterxml.jackson.*`) — only the annotations still come from `com.fasterxml`, which is
why `Sample` imports `JsonProperty` from there while everything else is `tools.jackson`.
`JsonMapperBuilderCustomizer` (in `org.springframework.boot.jackson.autoconfigure`) replaces
`Jackson2ObjectMapperBuilderCustomizer`, and it cannot set `StreamReadConstraints`:
`JsonMapper.Builder` takes its factory at construction and exposes no setter, so the parser
limits in `BrandApplication` have to redeclare the `JsonMapper.Builder` bean and re-apply
Boot's customizers by hand.

## Layout

Feature-per-package under `com.eland.brand`. `auth/` owns accounts and tokens: one service
(`AuthService`) behind two controllers (`AuthController` for login, `UserController` for
`/api/users`), because both are the same table and the same domain — do not split it into a
second service, the one-`ServiceTest`-per-package rule above depends on it.

`sample/` is the reference implementation of the full stack — `Sample` (POJO) → `SampleMapper` (+ XML) → `SampleService` → `SampleController`,
tested by `SampleServiceTest` alone. Copy this shape for new features; its runtime contract is
in [`okf/api/samples.md`](okf/api/samples.md).

No `@RestControllerAdvice`. `spring-boot-starter-validation` is not a dependency, so request
validation is an inline guard in the service, which is where the test can reach it.

**No DTO stands in for a domain class.** A request binds to the domain POJO — `Sample` and
`User` are what the controllers take — and a field that must not arrive from a request is
closed at the field (`User.role` is `READ_ONLY`), not by introducing a parallel type. The
two records in `auth/` are not that: `PasswordChange` carries `currentPassword` and
`newPassword`, which are not `User` fields and never become a row, and `AuthToken` is a
response with no table behind it at all. A record is right where the payload has no domain
class; it is wrong as a second shape for one that does.
