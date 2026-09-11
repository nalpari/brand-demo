---
type: PostgreSQL Table
title: sample
description: Reference table used to exercise the MyBatis stack end to end; not business data.
resource: postgresql://localhost:5432/appdb/public/sample
tags: [sample, reference]
generated: { by: claude-code/opus-5, at: 2026-09-01T08:20:58Z }
status: draft
sources:
  - id: live-schema
    resource: postgresql://localhost:5432/appdb/public/sample
    title: "psql \\d+ sample"
    author: process:psql
    last_modified: 2026-09-01T06:17:29Z
---

# Schema

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `bigint` | not null | `nextval('sample_id_seq')` | Surrogate primary key. Returned to the caller via MyBatis `useGeneratedKeys`. [^live-schema] |
| `name` | `text` | not null | — | Free-form label. The only field the API accepts on write. The column itself is unbounded; blank, NUL-bearing and over-20-code-point values are rejected in `SampleService` before insert, not by a check constraint — see [/api/samples](../api/samples.md). [^live-schema] |
| `created_at` | `timestamptz` | not null | `now()` | Insert time in UTC. Database-assigned; never written by the application. [^live-schema] |

Primary key: `sample_pkey` btree on `id`. No other indexes, no foreign keys.

# Provenance

The table was created by hand with `psql`. This repository has no migration
tool (no Flyway, no Liquibase, no JPA `ddl-auto`), so the DDL below is the
only record of it:

```sql
create table sample (
  id         bigserial primary key,
  name       text not null,
  created_at timestamptz not null default now()
);
```

Changing the schema means running DDL against the database *and* updating this
document — nothing in the repository reconciles the two.

# Access

Read and written through the [/api/samples endpoint](../api/samples.md). The SQL lives in
`src/main/resources/mapper/SampleMapper.xml`.

[^live-schema]: Read from the live database on 2026-09-01.
