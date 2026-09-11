# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

The git root is this directory, but the only project is `brand/` — the E-Land brand service
(Spring Boot 4, MyBatis, PostgreSQL, Java 17). Its `gradlew`, `build.gradle` and `.gitignore`
all live there, so **run every Gradle command from `brand/`** (`cd brand && ./gradlew test`).

Everything under `brand/` (its README, CLAUDE.md and the `okf/` bundle) was written with
`brand/` as the repository root. Where those docs say "repository root", read `brand/`:

- `.env` (`JWT_SECRET`, `CORS_ALLOWED_ORIGINS`) goes in `brand/.env`. `application.yaml`
  imports it relative to the process working directory, and `bootRun` runs in `brand/`.
- Relative links such as `okf/api/auth.md` resolve under `brand/`.
- The worktree procedure (`brand/okf/development/worktrees.md`) copies untracked files by
  repo-relative path. In a worktree of this repo those files belong under `<worktree>/brand/`,
  so prefix its copy list with `brand/` and run the loop from this directory.

Code-style conventions (formatting, visibility, null → 404 handling, test style, commit
format) are in `brand/docs/convention/coding-convention.html`.

## Project rules

@brand/CLAUDE.md
