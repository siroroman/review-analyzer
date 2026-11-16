"""`python -m app.storage`: apply the migrations in `migrations/` to the database in `DATABASE_URL`."""

import os
from collections.abc import Mapping

import psycopg

from app.storage._postgres import connect
from app.transport import read_secret


def main(environ: Mapping[str, str]) -> int:
    """Raises `MissingSecret` (naming the variable, never its value) when `DATABASE_URL` is not set."""
    db = connect(read_secret(environ, "DATABASE_URL").get_secret_value())
    try:
        with db.cursor() as cur:
            cur.execute("SELECT count(*) FROM schema_migrations")
            count = _count(cur)
    finally:
        db.close()
    print(f"database is up to date: {count} migrations applied")
    return 0


def _count(cur: "psycopg.Cursor[tuple[int]]") -> int:
    row = cur.fetchone()
    return row[0] if row else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(os.environ))
