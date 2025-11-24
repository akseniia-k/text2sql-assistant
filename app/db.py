# app/db.py
"""
Database execution helpers for the Text-to-SQL assistant.

Responsibilities:
- Create a SQLAlchemy engine for a SQLite database.
- Run SELECT queries safely (using sql_guard).
- Return pandas DataFrames + any error message.
"""

from __future__ import annotations
import argparse
from typing import Tuple, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.sql_guard import guard_sql, SqlGuardError


def _to_uri(path_or_uri: str) -> str:
    """Accept either a raw path or a full sqlite:/// URI and normalize."""
    return path_or_uri if path_or_uri.startswith("sqlite:///") else f"sqlite:///{path_or_uri}"


def create_sqlite_engine(path_or_uri: str) -> Engine:
    """
    Create a SQLAlchemy engine for a SQLite database.

    Example:
        engine = create_sqlite_engine("data/chinook.sqlite")
    """
    uri = _to_uri(path_or_uri)
    return create_engine(uri, future=True)


def safe_execute(
    engine: Engine,
    sql: str,
    apply_guard: bool = True,
    default_limit: int = 1000,
) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
    """
    Execute a (hopefully) SELECT query safely.

    Steps:
    - Optionally run the query through sql_guard (enforces SELECT-only, LIMIT, etc.).
    - Execute using pandas.read_sql_query.
    - Return (DataFrame_or_None, executed_sql, error_message_or_None).

    If an error occurs, DataFrame is None and error_message contains the exception text.
    """
    if not isinstance(sql, str):
        raise ValueError("sql must be a string")

    original_sql = sql.strip()

    try:
        final_sql = guard_sql(original_sql, default_limit=default_limit) if apply_guard else original_sql
    except SqlGuardError as e:
        # Guard rejected the query before hitting the DB.
        return None, original_sql, f"SQL rejected by guard: {e}"

    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(final_sql), conn)
        return df, final_sql, None
    except Exception as e:
        return None, final_sql, str(e)


# ----------------------
# CLI helper (optional)
# ----------------------

def _cli():
    """
    Small CLI utility to manually run a query:

      python -m app.db data/chinook.sqlite "SELECT Name FROM Artist LIMIT 5;"
    """
    parser = argparse.ArgumentParser(description="Run a safe SELECT query against a SQLite DB.")
    parser.add_argument("db_path", help="Path or sqlite:/// URI, e.g. data/chinook.sqlite")
    parser.add_argument("sql", help="SQL query to run (ideally a SELECT).")
    parser.add_argument("--no-guard", action="store_true", help="Disable sql_guard (not recommended).")
    args = parser.parse_args()

    engine = create_sqlite_engine(args.db_path)
    df, executed_sql, err = safe_execute(engine, args.sql, apply_guard=not args.no_guard)

    print(f"\nExecuted SQL:\n{executed_sql}\n")

    if err:
        print(f"❌ Error while executing query:\n{err}")
    else:
        print("✅ Query executed successfully. Top rows:\n")
        # Show first few rows
        print(df.head())

if __name__ == "__main__":
    _cli()
