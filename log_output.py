"""
Register a workflow output and/or notes into bernoulli-db.

outputs.db  →  one table per output type: lab_canon, lit_review, summary, deep_research
               each table: (slug VARCHAR UNIQUE, file_path VARCHAR, last_modified TIMESTAMP)

notes.db    →  single table: notes(slug, file_path, note_type, last_modified TIMESTAMP)

Both are DuckDB files. Idempotent — safe to run multiple times.

Usage:
  python log_output.py \
    --slug keller-canon \
    --type lab_canon \
    --file-path outputs/keller-canon.md \
    [--note "notes/keller-publications.md" publications] \
    [--note "notes/keller-*.md" research_sweep]

--note takes exactly two values: PATTERN NOTE_TYPE (glob patterns are expanded).
"""
from __future__ import annotations

import argparse
import glob
import sys
from datetime import datetime
from pathlib import Path

DB_DIR     = Path("/Users/harvest/nova/bernoulli-db")
OUTPUTS_DB = DB_DIR / "outputs.db"
NOTES_DB   = DB_DIR / "notes.db"

OUTPUT_TABLES = ("lab_canon", "lit_review", "summary", "deep_research")


_EXPECTED_COLS = {"slug", "file_path", "last_modified"}


def _table_cols(con, table: str) -> set[str]:
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ?", [table]
    ).fetchall()
    return {r[0] for r in rows}


def bootstrap_outputs(con) -> None:
    # Drop any stale tables not in OUTPUT_TABLES
    existing = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()}
    for stale in existing - set(OUTPUT_TABLES):
        con.execute(f"DROP TABLE IF EXISTS {stale}")

    for table in OUTPUT_TABLES:
        if table in existing and _table_cols(con, table) != _EXPECTED_COLS:
            con.execute(f"DROP TABLE {table}")
        con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                slug          VARCHAR UNIQUE NOT NULL,
                file_path     VARCHAR NOT NULL,
                last_modified TIMESTAMP NOT NULL
            )
        """)


def bootstrap_notes(con) -> None:
    expected = {"slug", "file_path", "note_type", "last_modified"}
    if _table_cols(con, "notes") != expected:
        con.execute("DROP TABLE IF EXISTS notes")
    con.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            slug          VARCHAR NOT NULL,
            file_path     VARCHAR UNIQUE NOT NULL,
            note_type     VARCHAR NOT NULL,
            last_modified TIMESTAMP NOT NULL
        )
    """)


def upsert_output(con, table: str, slug: str, file_path: str, now: datetime) -> bool:
    row = con.execute(f"SELECT slug FROM {table} WHERE slug = ?", [slug]).fetchone()
    if row:
        con.execute(
            f"UPDATE {table} SET file_path = ?, last_modified = ? WHERE slug = ?",
            [file_path, now, slug],
        )
        return False
    con.execute(
        f"INSERT INTO {table} (slug, file_path, last_modified) VALUES (?, ?, ?)",
        [slug, file_path, now],
    )
    return True


def upsert_note(con, slug: str, file_path: str, note_type: str, now: datetime) -> bool:
    row = con.execute("SELECT slug FROM notes WHERE file_path = ?", [file_path]).fetchone()
    if row:
        return False
    con.execute(
        "INSERT INTO notes (slug, file_path, note_type, last_modified) VALUES (?, ?, ?, ?)",
        [slug, file_path, note_type, now],
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a workflow output in bernoulli-db")
    parser.add_argument("--slug",      required=True, help="Workflow slug (e.g. keller-canon)")
    parser.add_argument("--type",      required=True, choices=list(OUTPUT_TABLES), dest="output_type",
                        help="Output type — determines which table in outputs.db")
    parser.add_argument("--file-path", required=True, dest="file_path",
                        help="Path to final output file")
    parser.add_argument("--note",      nargs=2, action="append", metavar=("PATTERN", "NOTE_TYPE"),
                        default=[],
                        help="Register note file(s); PATTERN may be a glob. Repeatable.")
    args = parser.parse_args()

    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb not installed — run: pip install duckdb", file=sys.stderr)
        sys.exit(1)

    now = datetime.now()

    # ── outputs.db ────────────────────────────────────────────────────────────
    con_out = duckdb.connect(str(OUTPUTS_DB))
    bootstrap_outputs(con_out)
    inserted = upsert_output(con_out, args.output_type, args.slug, args.file_path, now)
    con_out.close()
    action = "inserted" if inserted else "updated"
    print(f"✓ outputs.db  [{action}]  {args.output_type}.{args.slug}  →  {args.file_path}")

    # ── notes.db ──────────────────────────────────────────────────────────────
    if args.note:
        con_notes = duckdb.connect(str(NOTES_DB))
        bootstrap_notes(con_notes)
        for pattern, note_type in args.note:
            matched = sorted(glob.glob(pattern))
            if not matched:
                print(f"  note pattern matched nothing, skipping: {pattern}")
                continue
            for fpath in matched:
                new = upsert_note(con_notes, args.slug, fpath, note_type, now)
                status = "inserted" if new else "exists"
                print(f"  ✓ notes.db  [{status}]  {fpath}  [{note_type}]")
        con_notes.close()


if __name__ == "__main__":
    main()
