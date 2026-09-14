# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

The git root is this directory, but the only project is `brand/` — the E-Land brand service
(Spring Boot 4, MyBatis, PostgreSQL, Java 17). Its `gradlew`, `build.gradle` and `.gitignore`
all live there, so **run every Gradle command from `brand/`** (`cd brand && ./gradlew test`).

The `okf/` bundle lives here and is written with this directory as the root, so its paths
into the service carry a `brand/` prefix. `brand/`'s own README and CLAUDE.md were written
with `brand/` as the repository root. Where those say "repository root", read `brand/`:

- `.env` (`JWT_SECRET`, `CORS_ALLOWED_ORIGINS`) goes in `brand/.env`. `application.yaml`
  imports it relative to the process working directory, and `bootRun` runs in `brand/`.

Code-style conventions (formatting, visibility, null → 404 handling, test style, commit
format) are in `brand/docs/convention/coding-convention.html`.

## Worktrees

**사용자가 명시적으로 요청할 때만 만든다.** 브랜치를 새로 파거나 기능 작업을 해달라는 요청은
평소대로 git으로 처리한다.

| 플랫폼 | 위치 |
| --- | --- |
| Windows | `C:\workspace\.worktrees\eland\<관광명소>` |
| macOS / Linux | `~/.worktrees/eland/<관광명소>` |

- **워크트리 디렉터리 이름은 세계 관광명소**, 소문자 kebab-case: `machu-picchu`, `santorini`, `angkor-wat`
- **브랜치 이름은 포켓몬**, 소문자: `snorlax`, `gengar`, `lapras`

워크트리 생성·진입·정리 전에 [워크트리 절차](okf/development/worktrees.md)를 읽는다.
추적하지 않는 설정 파일을 추가하면 같은 변경에서 그 문서의 복사 목록도 갱신한다.

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

## Project rules

@brand/CLAUDE.md
