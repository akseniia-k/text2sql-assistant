"""
Thin CLI smoke test:
- reads schema text from a SQLite DB
- builds the full prompt (rules + schema + few-shots + user question)
- prints it to stdout (no model call yet)

Usage:
  python -m app.orchestrator "Which artist has the highest total invoice amount?"
  # optional custom DB path:
  python -m app.orchestrator --db data/chinook.sqlite "Your question here"
"""

from __future__ import annotations
import argparse
from textwrap import dedent
from app.schema_reader import get_schema_text
from app.prompt_builder import build_prompt

def main():
    parser = argparse.ArgumentParser(
        description="Smoke test: assemble prompt from schema + few-shots + question."
    )
    parser.add_argument(
        "question",
        help="User question in natural language, e.g. 'Which artist has the highest total invoice amount?'"
    )
    parser.add_argument(
        "--db",
        default="data/chinook.sqlite",
        help="Path (or sqlite:/// URI) to SQLite DB. Default: data/chinook.sqlite",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=1,
        help="Sample rows per table to include in schema text (0 to disable).",
    )
    parser.add_argument(
        "--max-tables",
        type=int,
        default=12,
        help="Max number of tables to include in schema text.",
    )
    parser.add_argument(
        "--max-cols",
        type=int,
        default=20,
        help="Max columns per table to include in schema text.",
    )
    args = parser.parse_args()

    # 1) Read compact schema text (for prompt)
    schema_text = get_schema_text(
        args.db,
        max_tables=args.max_tables,
        max_cols_per_table=args.max_cols,
        sample_rows_per_table=args.sample_rows,
        include_samples_in_markdown=bool(args.sample_rows > 0),
    )

    # 2) Build the full LLM prompt (rules + schema + examples + question)
    prompt = build_prompt(args.question, schema_text)

    # 3) Print it (no model call yet)
    print(dedent(prompt))

if __name__ == "__main__":
    main()
