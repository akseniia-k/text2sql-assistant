from __future__ import annotations
import argparse
from typing import Dict, List, Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

INTERNAL_TABLE_PREFIXES = ("sqlite_",)  # hide SQLite internals (e.g., sqlite_sequence)

def _to_uri(path_or_uri: str) -> str:
    """Accept either a raw path or a full sqlite:/// URI."""
    return path_or_uri if path_or_uri.startswith("sqlite:///") else f"sqlite:///{path_or_uri}"

def _is_internal_table(name: str) -> bool:
    return name.startswith(INTERNAL_TABLE_PREFIXES)

def read_schema(
    engine: Engine,
    include_views: bool = False,
    max_tables: int | None = 15,
    max_cols_per_table: int = 20,
    sample_rows_per_table: int = 0,
) -> Dict[str, Any]:
    """
    Reflect tables/columns/PK/FKs and (optionally) grab a few sample rows.
    Returns a dict:
    {
      "tables": {
        "<table>": {
          "columns": [{"name": ..., "type": ..., "nullable": ..., "default": ...}, ...],
          "primary_key": ["colA", "colB", ...],
          "foreign_keys": [{"column": ..., "referred_table": ..., "referred_columns": [...]}, ...],
          "samples": [ {col: val, ...}, ... ]  # optional, up to sample_rows_per_table
        },
        ...
      },
      "truncated": {"tables": bool, "columns": {table: bool}}
    }
    """
    insp = inspect(engine)
    all_tables = insp.get_table_names()
    if include_views:
        all_tables += insp.get_view_names()

    # filter internal tables (e.g. sqlite_sequence)
    all_tables = [t for t in all_tables if not _is_internal_table(t)]
    all_tables_sorted = sorted(all_tables)

    truncated_tables = False
    if max_tables is not None and len(all_tables_sorted) > max_tables:
        truncated_tables = True
        tables = all_tables_sorted[:max_tables]
    else:
        tables = all_tables_sorted

    result: Dict[str, Any] = {"tables": {}, "truncated": {"tables": truncated_tables, "columns": {}}}

    with engine.connect() as conn:
        for table in tables:
            cols_meta = insp.get_columns(table)
            pk_meta = insp.get_pk_constraint(table) or {}
            fk_meta = insp.get_foreign_keys(table) or []

            # columns (truncate if needed)
            columns = []
            truncated_cols = False
            for c in cols_meta[:max_cols_per_table]:
                columns.append(
                    {
                        "name": c.get("name"),
                        "type": str(c.get("type")),
                        "nullable": bool(c.get("nullable")),
                        "default": c.get("default"),
                    }
                )
            if len(cols_meta) > max_cols_per_table:
                truncated_cols = True
                result["truncated"]["columns"][table] = True

            # primary keys
            pk_cols = pk_meta.get("constrained_columns") or []

            # foreign keys
            fks = []
            for fk in fk_meta:
                fks.append(
                    {
                        "column": fk.get("constrained_columns", [None])[0],
                        "referred_table": fk.get("referred_table"),
                        "referred_columns": fk.get("referred_columns") or [],
                    }
                )

            # sample rows
            samples: List[dict] = []
            if sample_rows_per_table > 0:
                try:
                    q = text(f'SELECT * FROM "{table}" LIMIT :n')
                    rows = conn.execute(q, {"n": sample_rows_per_table}).mappings().all()
                    for r in rows:
                        samples.append(dict(r))
                except Exception:
                    # sampling is best-effort; ignore failures
                    pass

            result["tables"][table] = {
                "columns": columns,
                "primary_key": pk_cols,
                "foreign_keys": fks,
                "samples": samples,
                "_columns_truncated": truncated_cols,
            }

    return result

def schema_to_markdown(
    schema: Dict[str, Any],
    include_samples: bool = False,
    max_sample_value_len: int = 40,
) -> str:
    """
    Render a concise, LLM-friendly schema block.
    """
    lines: List[str] = []
    lines.append("### Database Schema (SQLite)")
    lines.append("Notes: Only use listed tables/columns. Prefer explicit JOINs.\n")

    for table in sorted(schema["tables"].keys()):
        t = schema["tables"][table]
        # columns line
        cols_list = [f'{c["name"]} {c["type"]}' for c in t["columns"]]
        cols_txt = ", ".join(cols_list)
        if t.get("_columns_truncated"):
            cols_txt += ", …"  # indicate truncation
        lines.append(f"- **{table}**: {cols_txt}")

        # PK
        if t["primary_key"]:
            lines.append(f"  - PK: {', '.join(t['primary_key'])}")

        # FKs
        if t["foreign_keys"]:
            fk_bits = []
            for fk in t["foreign_keys"]:
                col = fk["column"]
                ref_t = fk["referred_table"]
                ref_cols = ", ".join(fk["referred_columns"])
                fk_bits.append(f"{col} → {ref_t}({ref_cols})")
            lines.append("  - FK: " + "; ".join(fk_bits))

        # samples
        if include_samples and t["samples"]:
            for i, row in enumerate(t["samples"], 1):
                parts = []
                for k, v in row.items():
                    v_str = str(v)
                    if len(v_str) > max_sample_value_len:
                        v_str = v_str[: max_sample_value_len - 1] + "…"
                    parts.append(f"{k}={v_str}")
                lines.append(f"  - sample{'' if len(t['samples'])==1 else ' ' + str(i)}: " + ", ".join(parts))

    if schema["truncated"]["tables"]:
        lines.append("\n… (some tables omitted)")
    return "\n".join(lines)

def get_schema_text(
    path_or_uri: str,
    include_views: bool = False,
    max_tables: int | None = 12,
    max_cols_per_table: int = 20,
    sample_rows_per_table: int = 0,
    include_samples_in_markdown: bool = False,
) -> str:
    engine = create_engine(_to_uri(path_or_uri))
    schema = read_schema(
        engine,
        include_views=include_views,
        max_tables=max_tables,
        max_cols_per_table=max_cols_per_table,
        sample_rows_per_table=sample_rows_per_table,
    )
    return schema_to_markdown(schema, include_samples=include_samples_in_markdown)

def _cli():
    p = argparse.ArgumentParser(description="Reflect a SQLite schema and print a compact markdown summary.")
    p.add_argument("db_path", help="Path or sqlite:/// URI, e.g., data/chinook.sqlite")
    p.add_argument("--include-views", action="store_true", help="Include SQLite views")
    p.add_argument("--max-tables", type=int, default=12, help="Max number of tables to include (default 12)")
    p.add_argument("--max-cols", type=int, default=20, help="Max columns per table (default 20)")
    p.add_argument("--sample-rows", type=int, default=1, help="Sample rows per table (0 to disable)")
    p.add_argument("--show-samples", action="store_true", help="Include sample rows in the markdown")
    args = p.parse_args()

    engine = create_engine(_to_uri(args.db_path))
    schema = read_schema(
        engine,
        include_views=args.include_views,
        max_tables=args.max_tables,
        max_cols_per_table=args.max_cols,
        sample_rows_per_table=args.sample_rows,
    )
    md = schema_to_markdown(schema, include_samples=args.show_samples)
    print(md)

if __name__ == "__main__":
    _cli()
