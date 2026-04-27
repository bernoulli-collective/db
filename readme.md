### Bernoulli db

Small DuckDB registry for Bernoulli notes and outputs

## Databases

`outputs.db` stores one table per output type:

- `lab_canon`
- `lit_review`
- `summary`
- `deep_research`

Each output table has:

```sql
slug VARCHAR UNIQUE NOT NULL,
file_path VARCHAR NOT NULL,
last_modified TIMESTAMP NOT NULL
```

`notes.db` stores supporting notes in a single `notes` table:

```sql
slug VARCHAR NOT NULL,
file_path VARCHAR UNIQUE NOT NULL,
note_type VARCHAR NOT NULL,
last_modified TIMESTAMP NOT NULL
```

## Setup

Install DuckDB for Python:

```bash
pip install duckdb
```

Optional DuckDB CLI usage:

```bash
duckdb outputs.db
duckdb notes.db
```

## Register An Output

Use `log_output.py` to create or update an output record. The script is idempotent, so it is safe to run more than once for the same slug.

```bash
python log_output.py \
  --slug keller-canon \
  --type lab_canon \
  --file-path outputs/keller-canon.md
```

Register notes at the same time with repeatable `--note PATTERN NOTE_TYPE` arguments:

```bash
python log_output.py \
  --slug keller-canon \
  --type lab_canon \
  --file-path outputs/keller-canon.md \
  --note "notes/keller-publications.md" publications \
  --note "notes/keller-*.md" research_sweep
```

`--type` must be one of `lab_canon`, `lit_review`, `summary`, or `deep_research`.

## Inspect With DuckDB SQL

List tables:

```sql
SHOW TABLES;
```

Show table contents:

```sql
SELECT * FROM lab_canon;
SELECT * FROM lit_review;
SELECT * FROM summary;
SELECT * FROM deep_research;
```

Preview rows:

```sql
SELECT * FROM lab_canon LIMIT 20;
```

Inspect schema:

```sql
DESCRIBE lab_canon;
```

For notes:

```bash
duckdb notes.db
```

```sql
SHOW TABLES;
SELECT * FROM notes;
DESCRIBE notes;
```

