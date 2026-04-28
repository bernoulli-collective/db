"""
Sync ../bernoulli outputs and notes into DuckDB registries.

Outputs are written to outputs.db; notes are written to notes.db.
"""
from __future__ import annotations

import sys
from pathlib import Path
import inspect_database

DB_DIR = Path(__file__).resolve().parent
BERNOULLI_DIR = DB_DIR.parent / "bernoulli"
OUTPUTS_DB = DB_DIR / "outputs.db"
NOTES_DB = DB_DIR / "notes.db"

OUTPUT_TABLES = ("lab_canon", "lit_review", "summary", "deep_research")
OUTPUT_SUFFIXES = {
    "-canon": "lab_canon",
    "-lit-review": "lit_review",
    "-literature-review": "lit_review",
    "-summary": "summary",
    "-deep-research": "deep_research",
}
SKIP_OUTPUT_SUFFIXES = (".provenance", "outreach", "diagram", "_review")


def slug_for_output(path: Path) -> str:
    stem = path.stem
    for suffix in OUTPUT_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def table_for_output(path: Path) -> str | None:
    stem = path.stem
    if stem.endswith(SKIP_OUTPUT_SUFFIXES):
        return None
    for suffix, table in OUTPUT_SUFFIXES.items():
        if stem.endswith(suffix):
            return table
    return "deep_research"


def note_type_for(stem: str, slug: str) -> str:
    prefix = f"{slug}-"
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem.rsplit("-", 1)[-1]


def bootstrap_outputs(con) -> None:
    for table in OUTPUT_TABLES:
        con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                slug          VARCHAR UNIQUE NOT NULL,
                file_path     VARCHAR NOT NULL,
                last_modified TIMESTAMP NOT NULL
            )
        """)
        con.execute(f"DELETE FROM {table}")


def bootstrap_notes(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            slug          VARCHAR NOT NULL,
            file_path     VARCHAR UNIQUE NOT NULL,
            note_type     VARCHAR NOT NULL,
            last_modified TIMESTAMP NOT NULL
        )
    """)
    con.execute("DELETE FROM notes")


def rel(path: Path) -> str:
    return str(path.relative_to(BERNOULLI_DIR))


def main() -> None:
    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb not installed - run: pip install duckdb", file=sys.stderr)
        sys.exit(1)


    # in source directory
    outputs_dir = BERNOULLI_DIR / "outputs"
    notes_dir = BERNOULLI_DIR / "notes"

    outputs = []
    output_slugs = set()
    for path in sorted(outputs_dir.glob("*.md")):
        table = table_for_output(path)
        if table is None:
            continue
        slug = slug_for_output(path)
        output_slugs.add(slug)
        outputs.append((table, slug, rel(path), path.stat().st_mtime))

    notes = []
    for path in sorted(notes_dir.glob("*.md")):
        stem = path.stem
        slug = max((s for s in output_slugs if stem.startswith(f"{s}-")), key=len, default=None)
        slug = slug or stem.rsplit("-", 1)[0]
        notes.append((slug, rel(path), note_type_for(stem, slug), path.stat().st_mtime))

    con_out = duckdb.connect(str(OUTPUTS_DB))
    bootstrap_outputs(con_out)
    for table, slug, file_path, modified in outputs:
        con_out.execute(
            f"""
            INSERT INTO {table} (slug, file_path, last_modified)
            VALUES (?, ?, to_timestamp(?))
            """,
            [slug, file_path, modified],
        )
    inspect_database.inspect_database(con_out)
    con_out.close()

    con_notes = duckdb.connect(str(NOTES_DB))
    bootstrap_notes(con_notes)
    for row in notes:
        con_notes.execute(
            """
            INSERT INTO notes (slug, file_path, note_type, last_modified)
            VALUES (?, ?, ?, to_timestamp(?))
            """,
            row,
        )
    inspect_database.inspect_database(con_notes)
    con_notes.close()

    print(f"synced {len(outputs)} outputs and {len(notes)} notes")


if __name__ == "__main__":
    main()
