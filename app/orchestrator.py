# app/orchestrator.py
"""
End-to-end CLI pipeline for the Text-to-SQL assistant.

Flow:
  user question
    → read DB schema (schema_reader.get_schema_text)
    → build full prompt (prompt_builder.build_prompt)
    → call LLM to generate SQL (llm_client.LLMClient)
    → guard SQL for safety (inside db.safe_execute)
    → execute on SQLite DB
    → print SQL + top rows or error

Usage examples:

  # Basic run on Chinook
  python -m app.orchestrator "Which artist has the highest total invoice amount?"

  # Different DB file
  python -m app.orchestrator --db data/chinook.sqlite "List the 5 most expensive tracks."

  # Just print the prompt (no LLM, no DB)
  python -m app.orchestrator --dry-run "Which artist has the most albums?"
"""

from __future__ import annotations
import argparse
from textwrap import dedent

from tabulate import tabulate

from app.schema_reader import get_schema_text
from app.prompt_builder import build_prompt
from app.llm_client import LLMClient
from app.db import create_sqlite_engine, safe_execute


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end Text-to-SQL CLI (question → prompt → LLM → SQL → DB results)."
    )
    parser.add_argument(
        "question",
        help="User question in natural language, e.g. 'Which artist has the highest total invoice amount?'",
    )
    parser.add_argument(
        "--db",
        default="data/chinook.sqlite",
        help="Path or sqlite:/// URI to SQLite DB. Default: data/chinook.sqlite",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model name (e.g., gpt-4o-mini, gpt-4.1). Default: gpt-4o-mini",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (0.0 = more deterministic). Default: 0.0",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only build and print the prompt; do not call the LLM or execute SQL.",
    )
    args = parser.parse_args()

    # 1) Read compact schema text (for the prompt)
    print("🔍 Reading database schema...")
    schema_text = get_schema_text(
        args.db,
        max_tables=args.max_tables,
        max_cols_per_table=args.max_cols,
        sample_rows_per_table=args.sample_rows,
        include_samples_in_markdown=bool(args.sample_rows > 0),
    )

    # 2) Build full LLM prompt
    print("🧱 Building prompt...")
    prompt = build_prompt(args.question, schema_text)

    if args.dry_run:
        print("\n================ PROMPT (dry run) ================\n")
        print(dedent(prompt))
        print("\n==================================================")
        return

    # 3) Call the LLM to generate SQL
    print(f"🤖 Calling LLM model '{args.model}'...")
    client = LLMClient(model=args.model, temperature=args.temperature)
    raw_sql = client.generate_sql(prompt)

    print("\n---------------- Generated SQL (raw) -------------")
    print(raw_sql)
    print("-------------------------------------------------\n")

    # 4) Execute SQL safely against the DB
    print("🗄️  Executing SQL against database (with guard)...")
    engine = create_sqlite_engine(args.db)
    df, executed_sql, err = safe_execute(engine, raw_sql)

    print("\n---------------- Executed SQL --------------------")
    print(executed_sql)
    print("-------------------------------------------------\n")

    # 5) Show results or error
    if err:
        print("❌ Error executing query:")
        print(err)
    else:
        if df is None or df.empty:
            print("✅ Query executed successfully, but returned no rows.")
        else:
            print(f"✅ Query executed successfully. Showing top {min(10, len(df))} rows:\n")
            print(tabulate(df.head(10), headers="keys", tablefmt="psql"))


if __name__ == "__main__":
    main()
