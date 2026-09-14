---
type: PostgreSQL Table
title: users
description: Login accounts and their role. The source of identity for every JWT, and the row a token is re-checked against on each request.
resource: postgresql://localhost:5432/appdb/public/users
tags: [users, auth]
generated: { by: claude-code/opus-5, at: 2026-09-11T07:02:03Z }
status: draft
sources:
  - id: live-schema
    resource: postgresql://localhost:5432/appdb/public/users
    title: "psql \\d users"
    author: process:psql
    last_modified: 2026-09-08T03:32:00Z
---

# Schema

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `bigint` | not null | `nextval('users_id_seq')` | Surrogate primary key. Nothing outside the table references it — the JWT's `sub` claim carries `username`, not this. [^live-schema] |
| `username` | `text` | not null | — | The login name, unique. Goes into the token's `sub` claim verbatim. [^live-schema] |
| `password_hash` | `text` | not null | — | BCrypt hash from `BCryptPasswordEncoder` (`$2a$10$…`). Never leaves the process: `User.passwordHash` is `@JsonIgnore`. [^live-schema] |
| `created_at` | `timestamptz` | not null | `now()` | Insert time in UTC. Database-assigned. [^live-schema] |
| `role` | `text` | not null | `'USER'` | `USER` or `ADMIN`, enforced by a check constraint. An `ADMIN` may read, re-password and delete any account; a `USER` only their own. Read from this column on every such call, never from the token, so a promotion or demotion takes effect on the next request. [^live-schema] |
| `password_changed_at` | `timestamptz` | not null | `now()` | A token whose `iat` is earlier than this is refused. Written by `updatePassword` with `clock_timestamp()`, never by a request. The column default stays `now()` because an insert has nothing to race. [^live-schema] |

Primary key: `users_pkey` btree on `id`. Unique constraint: `users_username_key` btree on
`username`. Check constraint: `users_role_check` on `role in ('USER','ADMIN')`. No foreign
keys — nothing else in the schema is owned by a user yet.

There is no `enabled` or `locked` column: an account that should stop working is deleted,
which strands its tokens immediately (see `password_changed_at` above). Nothing here
supports a temporary suspension, and adding one means a column *and* a rule that reads it —
a column no rule reads is a claim about authorization the service does not make.

# Provenance

Created by hand with `psql`, like [sample](sample.md). This repository has no migration
tool, so the DDL below is the only record of it:

```sql
create table users (
  id            bigserial primary key,
  username      text not null unique,
  password_hash text not null,
  created_at    timestamptz not null default now()
);

-- added with the account CRUD endpoints
alter table users add column role text not null default 'USER'
  check (role in ('USER', 'ADMIN'));
alter table users add column password_changed_at timestamptz not null default now();
```

# Creating an account, and making one an admin

Accounts come from [`POST /api/users`](../api/users.md), which is anonymous — no `psql`
step is needed to get the first one.

**`role` cannot be set through the API at any point.** Signup forces `USER` and no endpoint
writes the column, so promotion is a database statement and a deliberate act:

```sql
update users set role = 'ADMIN' where username = 'alice';
```

It takes effect on that account's next request; no re-login is needed, because the rules
read this column rather than a claim in the token.

Inserting an account by hand still works and is the fallback when the API is not running.
The hash must be BCrypt — PostgreSQL will store a plaintext password happily and every
login against it then fails for a reason the logs do not explain. `htpasswd` (ships with
macOS at `/usr/sbin/htpasswd`) generates one without a Java round-trip; it emits the `$2y$`
prefix, which `BCryptPasswordEncoder` also accepts, but `$2a$` is what the application
writes, so normalize it and keep one shape in the column:

```bash
htpasswd -bnBC 10 "" 'correct-horse' | tr -d ':\n' | sed 's/^\$2y/\$2a/'
# $2a$10$CM9d6BfjDD3N3jsC8ErJMeD8xtsd83EKSVE3QxQLJZMCqMlH8fOcW
```

```sql
insert into users (username, password_hash) values ('alice', '$2a$10$...');
```

# Access

All of it through `UserMapper` (`brand/src/main/resources/mapper/UserMapper.xml`), called only by
`AuthService`: `insert` on signup, `updatePassword` and `deleteById` from the account
endpoints, `findByUsername` on login and on the `?username=` lookup, and `findById` on
signup's re-read for the defaulted columns and when an admin opens another account by id.

`updatePassword` stamps `password_changed_at` with **`clock_timestamp()`, not `now()`**.
`now()` is the transaction's start time, and `changePassword` opens its transaction before
two BCrypt rounds — so `now()` would record the revocation cutoff roughly 200ms before the
password actually changed. A login with the old password landing inside that window gets an
`iat` that is not earlier than the cutoff, and its token would survive the change for the
token's full lifetime. `AuthServiceTest.aChangedPasswordStrandsTokensIssuedBeforeIt` fails
if this is reverted to `now()`.

`updatePassword` also carries the hash the caller's `currentPassword` was checked against
in its **predicate** — `where id = ? and password_hash = ?`, not `where id = ?` alone.
`changePassword` reads the row and then spends two BCrypt rounds before writing, so another
change can commit in that gap; a bare `where id` update would overwrite it with a password
proved against a hash that is no longer current, and re-stamp `password_changed_at`,
stranding the tokens the winning change had just issued. The guard makes the losing write
touch no row, which the service reports as `409`.
`AuthServiceTest.aPasswordChangeThatVerifiedAHashTheRowNoLongerHasIsRefused` fails if the
predicate is reduced back to `id`.

`currentInstant` (`select clock_timestamp()`) runs once per login, **before**
`findByUsername` rather than after it. The row carries the revocation cutoff, so reading the
clock second would date the token after a cutoff the login never saw and `isTokenStale`
would then accept it for its full hour — a password change failing to strand a token minted
with the old password. Read first, both branches fall closed: a change landing before the
row read shows up as the new hash and fails the password check, and one landing after leaves
`iat` earlier than the new cutoff. The token's `iat` is
read from it rather than from the application clock, so the same clock that writes this
column also stamps the value it is compared against; see [/api/auth](../api/auth.md).

`findByUsername` also runs **at least once per authenticated request** — the JWT decoder
consults it to see whether the account still exists and whether the token predates the last
password change. That read is the standing cost of revoking a stateless token. An account
endpoint runs it a second time in `requireCaller`, because the decoder's copy is not carried
forward, and an admin opening another account by id adds a `findById` on top; see
[/api/auth](../api/auth.md).

[^live-schema]: Read from the live database on 2026-09-08.
