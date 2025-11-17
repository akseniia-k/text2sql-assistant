"""
SQL guardrail for your Text-to-SQL assistant.

Goals:
- Enforce SELECT-only (allow WITH ... SELECT).
- Deny common dangerous keywords (DDL/DML/pragma).
- Forbid multiple statements (no stacked queries).
- Ensure a LIMIT (append LIMIT 1000 if missing).
- Preserve a single trailing semicolon (optional).

This is a pragmatic, regex-first approach — not a full SQL parser — tuned for SQLite.
"""

from __future__ import annotations
import re
from typing import Tuple

# Case-insensitive and dotall flags reused
_RE_FLAGS = re.IGNORECASE | re.MULTILINE | re.DOTALL

# Denylist: extend if you need to be stricter
DENYLIST = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|ATTACH|PRAGMA|VACUUM|REINDEX|REPLACE|CREATE|TRIGGER|GRANT|REVOKE)\b",
    _RE_FLAGS,
)

# Matches SQL single-line and block comments (naive but effective for our guard)
RE_LINE_COMMENT = re.compile(r"--[^\n]*", _RE_FLAGS)
RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", _RE_FLAGS)

# Find first non-whitespace token
RE_FIRST_TOKEN = re.compile(r"^\s*([A-Za-z_]+)", _RE_FLAGS)

# LIMIT detection anywhere (good enough for guard purposes)
RE_LIMIT = re.compile(r"\bLIMIT\b\s+\d+", _RE_FLAGS)

# Collapse whitespace helper
RE_WS = re.compile(r"\s+", _RE_FLAGS)


class SqlGuardError(Exception):
    """Base class for SQL guard errors."""


class NotSelectError(SqlGuardError):
    """SQL is not a SELECT (or WITH ... SELECT)."""


class DangerousKeywordError(SqlGuardError):
    """SQL contains a deny-listed keyword."""


class MultipleStatementsError(SqlGuardError):
    """SQL contains multiple statements (stacked queries)."""


def _strip_comments(sql: str) -> str:
    """Remove -- line comments and /* block */ comments."""
    sql = RE_BLOCK_COMMENT.sub(" ", sql)
    sql = RE_LINE_COMMENT.sub(" ", sql)
    return sql


def _normalize_spaces(sql: str) -> str:
    return RE_WS.sub(" ", sql).strip()


def _single_statement_only(sql: str) -> str:
    """
    Ensure there's at most one SQL statement.
    Strategy: split on semicolons and ensure only one non-empty chunk.
    Returns SQL without internal semicolons; keeps an optional final semicolon.
    """
    # Keep one optional trailing semicolon, but forbid additional ones
    parts = [p.strip() for p in sql.split(";")]
    non_empty = [p for p in parts if p]
    if len(non_empty) > 1:
        raise MultipleStatementsError("Multiple SQL statements detected; only one SELECT is allowed.")

    # Rebuild: if original ended with semicolon, keep a single trailing ';'
    ends_with = sql.rstrip().endswith(";")
    core = non_empty[0] if non_empty else ""
    return (core + (";" if ends_with and core else "")).strip()


def _is_select_like(sql_no_comments: str) -> bool:
    """
    Accept:
      - SELECT ...
      - WITH cte AS (...) SELECT ...
    Reject everything else.
    """
    first = RE_FIRST_TOKEN.search(sql_no_comments)
    if not first:
        return False
    token = first.group(1).lower()
    if token == "select":
        return True
    if token == "with":
        # Heuristic: must contain a SELECT somewhere after WITH
        return bool(re.search(r"\bSELECT\b", sql_no_comments, _RE_FLAGS))
    return False


def _has_dangerous_keywords(sql_no_comments: str) -> bool:
    return bool(DENYLIST.search(sql_no_comments))


def _ensure_limit(sql: str, default_limit: int = 1000) -> str:
    """
    If no LIMIT appears anywhere, append LIMIT {default_limit} before final semicolon (if any).
    This is a pragmatic guard; it doesn't check subquery/top-level distinctions.
    """
    # Preserve single trailing semicolon while editing
    ends_with_semicolon = sql.rstrip().endswith(";")
    core = sql.rstrip(";").rstrip()

    if not RE_LIMIT.search(core):
        core = f"{core} LIMIT {default_limit}"

    return (core + (";" if ends_with_semicolon else "")).strip()


def guard_sql(sql: str, default_limit: int = 1000) -> str:
    """
    Main entry point:
      - strips comments
      - forbids stacked statements
      - denies dangerous keywords  ← check this first (so UPDATE/DELETE raise DangerousKeywordError)
      - enforces SELECT-only (or WITH ... SELECT)
      - ensures a LIMIT
      - returns the safe SQL string

    Raises SqlGuardError subclasses on failure.
    """
    if not isinstance(sql, str):
        raise SqlGuardError("SQL must be a string.")

    # Remove comments for analysis
    no_comments = _strip_comments(sql)

    # Forbid multiple statements
    single = _single_statement_only(no_comments)

    # 1) Deny dangerous keywords first (so UPDATE/DELETE/etc. map to DangerousKeywordError)
    if _has_dangerous_keywords(single):
        raise DangerousKeywordError("Query contains a forbidden keyword (DDL/DML/PRAGMA, etc.).")

    # 2) Then enforce SELECT-only (allows WITH ... SELECT)
    if not _is_select_like(single):
        raise NotSelectError("Only SELECT queries are allowed (WITH ... SELECT is permitted).")

    # Normalize whitespace
    single = _normalize_spaces(single)

    # Ensure a LIMIT
    single = _ensure_limit(single, default_limit=default_limit)

    # Ensure at most one trailing semicolon
    single = _single_statement_only(single)

    return single

