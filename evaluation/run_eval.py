# evaluation/run_eval.py
"""
Evaluation scaffolding for Text-to-SQL.

This file intentionally avoids calling any LLM. It provides:
- JSONL loading/validation for QA pairs
- Function signatures for:
    * exact_match(pred_sql, gold_sql)
    * execution_success(engine, sql)
    * result_equivalence(engine, pred_sql, gold_sql)
- A CLI to validate the JSONL and optionally sanity-check gold SQL on a DB.

Usage:
  # Structure-only validation
  python -m evaluation.run_eval --validate evaluation/qa_pairs.jsonl

  # Optional: execute gold SQL on Chinook as a sanity check
  python -m evaluation.run_eval --validate evaluation/qa_pairs.jsonl --db data/chinook.sqlite --sanity
"""

from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass
class QAPair:
    question: str
    sql: str


# ------------------------
# JSONL loading & checks
# ------------------------

def load_qa_pairs(path: str | Path) -> List[QAPair]:
    """Load question/SQL pairs from a JSONL file."""
    items: List[QAPair] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {i}: {e}") from e
            if "question" not in obj or "sql" not in obj:
                raise ValueError(f"Missing 'question' or 'sql' on line {i}")
            q = str(obj["question"]).strip()
            s = str(obj["sql"]).strip()
            if not q or not s:
                raise ValueError(f"Empty 'question' or 'sql' on line {i}")
            items.append(QAPair(question=q, sql=s))
    return items


def validate_qa_pairs(pairs: Iterable[QAPair]) -> Tuple[int, int]:
    """
    Return (n_pairs, n_duplicates) based on identical (question, sql).
    Simple sanity metric; expand as needed.
    """
    seen = set()
    dupes = 0
    n = 0
    for p in pairs:
        n += 1
        key = (p.question, p.sql)
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
    return n, dupes


# ------------------------
# Metric function signatures
# ------------------------

def exact_match(pred_sql: str, gold_sql: str) -> bool:
    """
    String-level comparison, normalized.
    Use only when the SQL is *deterministically* defined.
    """
    def norm(s: str) -> str:
        return " ".join(s.lower().replace("\n", " ").split()).strip().rstrip(";")
    return norm(pred_sql) == norm(gold_sql)


def execution_success(engine: Engine, sql: str) -> Tuple[bool, str | None]:
    """
    Attempt to execute SQL. Returns (success, error_message_or_none).
    The caller can decide whether to examine DataFrame results.
    """
    try:
        with engine.connect() as conn:
            # Use pandas for convenience; many metrics will want DataFrames
            pd.read_sql_query(text(sql), conn)
        return True, None
    except Exception as e:
        return False, str(e)


def result_equivalence(
    engine: Engine,
    pred_sql: str,
    gold_sql: str,
    sort_by: List[str] | None = None,
) -> bool:
    """
    Execute both queries and compare their results after sorting.
    If sort_by is None, sort by all columns lexicographically.

    NOTE: This is a pragmatic comparator; for large outputs, consider hashing.
    """
    def fetch(sql: str) -> pd.DataFrame:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(sql), conn)
        if sort_by:
            missing = [c for c in sort_by if c not in df.columns]
            if missing:
                # If requested sort columns are absent, fall back to all columns
                df = df.sort_values(list(df.columns)).reset_index(drop=True)
            else:
                df = df.sort_values(sort_by).reset_index(drop=True)
        else:
            df = df.sort_values(list(df.columns)).reset_index(drop=True) if len(df.columns) else df
        return df

    try:
        pred_df = fetch(pred_sql)
        gold_df = fetch(gold_sql)
    except Exception:
        return False

    # Compare shape + values
    if pred_df.shape != gold_df.shape:
        return False
    try:
        pd.testing.assert_frame_equal(pred_df.reset_index(drop=True), gold_df.reset_index(drop=True), check_dtype=False)
        return True
    except AssertionError:
        return False


# ------------------------
# CLI
# ------------------------

def _cli():
    ap = argparse.ArgumentParser(description="Validate evaluation/qa_pairs.jsonl and (optionally) sanity-check gold SQL.")
    ap.add_argument("--validate", required=True, help="Path to qa_pairs.jsonl")
    ap.add_argument("--db", help="Path or sqlite:/// URI to a SQLite DB (optional).")
    ap.add_argument("--sanity", action="store_true", help="If set with --db, executes gold SQL to ensure they run.")
    args = ap.parse_args()

    pairs = load_qa_pairs(args.validate)
    n, dupes = validate_qa_pairs(pairs)
    print(f"✅ Loaded {n} QA pairs ({dupes} duplicates). Structure looks good.")

    if args.db and args.sanity:
        uri = args.db if args.db.startswith("sqlite:///") else f"sqlite:///{args.db}"
        engine = create_engine(uri)
        ok = 0
        for i, p in enumerate(pairs, start=1):
            success, err = execution_success(engine, p.sql)
            if success:
                ok += 1
            else:
                print(f"❌ Line {i} failed to execute: {err}")
        print(f"Sanity: {ok}/{n} gold queries executed successfully.")

if __name__ == "__main__":
    _cli()
