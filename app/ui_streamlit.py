"""
Streamlit UI for the Text-to-SQL assistant.

Flow:
  - User selects DB (default: Chinook) and types a question.
  - App reads schema, builds prompt, calls LLM, guards/executes SQL.
  - UI shows: generated SQL, results table, schema, and prompt (optional).

Run with:
    streamlit run app/ui_streamlit.py
from the project root.
"""

from __future__ import annotations

# --- add this block at the very top ---
import os
import sys

# Add project root to sys.path so "import app.XXX" works when Streamlit runs this file
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# --- end of added block ---

import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.schema_reader import get_schema_text
from app.prompt_builder import build_prompt
from app.llm_client import LLMClient
from app.db import create_sqlite_engine, safe_execute


# -----------------------
# Streamlit configuration
# -----------------------

st.set_page_config(
    page_title="Text-to-SQL Assistant",
    page_icon="🧠",
    layout="wide",
)


# -----------------------
# Helpers
# -----------------------

def _ensure_uploaded_db_file(uploaded_file) -> str:
    """
    Save an uploaded SQLite file to a temp location and return its path.
    """
    suffix = Path(uploaded_file.name).suffix or ".sqlite"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.flush()
    tmp.close()
    return tmp.name


@st.cache_data(show_spinner=False)
def load_schema_text(db_path: str, sample_rows: int, max_tables: int, max_cols: int) -> str:
    """
    Cached wrapper around get_schema_text to avoid re-reflecting the DB on every run.
    """
    return get_schema_text(
        db_path,
        max_tables=max_tables,
        max_cols_per_table=max_cols,
        sample_rows_per_table=sample_rows,
        include_samples_in_markdown=bool(sample_rows > 0),
    )


# -----------------------
# Sidebar controls
# -----------------------

with st.sidebar:
    st.title("⚙️ Settings")

    # Database selection
    st.subheader("Database")

    default_db_path = "data/chinook.sqlite"
    use_default_db = st.radio(
        "Choose database source:",
        ["Default Chinook", "Upload SQLite file"],
        index=0,
    )

    uploaded_db = None
    if use_default_db == "Upload SQLite file":
        uploaded_db = st.file_uploader("Upload a .sqlite / .db file", type=["sqlite", "db"])

    # Model settings
    st.subheader("Model")
    model_name = st.selectbox(
        "Model",
        options=["gpt-4o-mini", "gpt-4.1"],
        index=0,
    )
    temperature = st.slider(
        "Temperature (0 = more deterministic)",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.1,
    )

    # Schema settings
    st.subheader("Schema settings")
    sample_rows = st.number_input("Sample rows per table", min_value=0, max_value=5, value=1, step=1)
    max_tables = st.number_input("Max tables in schema", min_value=1, max_value=50, value=12, step=1)
    max_cols = st.number_input("Max columns per table", min_value=1, max_value=50, value=20, step=1)

    st.markdown("---")
    st.caption("Tip: use the default Chinook DB while developing.")


# -----------------------
# Main layout
# -----------------------

st.title("🧠 Text-to-SQL Assistant")
st.write(
    "Ask questions in natural language and get **SQL + results** from a SQLite database. "
    "The app shows the generated SQL, results, and the underlying schema for transparency."
)

# Question input
question = st.text_input(
    "Your question",
    placeholder="E.g. Which artist has the highest total invoice amount?",
)

run_button = st.button("Run query", type="primary")

# Prepare space for outputs
sql_col, result_col = st.columns([1, 2])

# Initialize history in session state
if "history" not in st.session_state:
    st.session_state["history"] = []


# -----------------------
# Main interaction
# -----------------------

if run_button:
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        # Determine DB path
        if use_default_db == "Default Chinook":
            db_path = default_db_path
        else:
            if uploaded_db is None:
                st.error("Please upload a SQLite database file.")
                st.stop()
            db_path = _ensure_uploaded_db_file(uploaded_db)

        # 1) Read schema
        with st.spinner("Reading database schema..."):
            try:
                schema_text = load_schema_text(
                    db_path=db_path,
                    sample_rows=sample_rows,
                    max_tables=max_tables,
                    max_cols=max_cols,
                )
            except Exception as e:
                st.error(f"Failed to read schema from database: {e}")
                st.stop()

        # 2) Build prompt
        with st.spinner("Building prompt..."):
            prompt = build_prompt(question, schema_text)

        # 3) Call LLM
        with st.spinner(f"Calling LLM model '{model_name}'..."):
            try:
                client = LLMClient(model=model_name, temperature=temperature)
                raw_sql = client.generate_sql(prompt)
            except Exception as e:
                st.error(f"Error while calling LLM: {e}")
                st.stop()

        # 4) Execute SQL
        with st.spinner("Executing SQL against database..."):
            try:
                engine = create_sqlite_engine(db_path)
                df, executed_sql, err = safe_execute(engine, raw_sql)
            except Exception as e:
                df, executed_sql, err = None, raw_sql, str(e)

        # Store history
        st.session_state["history"].append(
            {
                "question": question,
                "raw_sql": raw_sql,
                "executed_sql": executed_sql,
                "error": err,
                "row_count": None if df is None else len(df),
            }
        )

        # 5) Show SQL and results
        with sql_col:
            st.subheader("Generated SQL")
            st.code(raw_sql or "", language="sql")

            st.subheader("Executed SQL (after guard)")
            st.code(executed_sql or "", language="sql")

        with result_col:
            st.subheader("Results")
            if err:
                st.error(err)
            else:
                if df is None or df.empty:
                    st.info("Query executed successfully, but returned no rows.")
                else:
                    st.success(f"Query executed successfully. Rows: {len(df)}")
                    st.dataframe(df)

                    # Download button
                    csv_data = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="Download results as CSV",
                        data=csv_data,
                        file_name="query_results.csv",
                        mime="text/csv",
                    )

        # Optional: show schema and prompt in expanders
        with st.expander("📚 Show database schema (for the model)"):
            st.markdown(schema_text)

        with st.expander("🧾 Show full prompt (debug)"):
            st.text(prompt)


# -----------------------
# History panel
# -----------------------

st.markdown("---")
st.subheader("History (this session)")

if not st.session_state["history"]:
    st.caption("No queries yet.")
else:
    # Show a compact table of past questions & status
    hist_df = pd.DataFrame(
        [
            {
                "Question": h["question"],
                "Rows": h["row_count"],
                "Error?": bool(h["error"]),
            }
            for h in st.session_state["history"]
        ]
    )
    st.dataframe(hist_df, use_container_width=True)

    # Optionally show last raw SQL in an expander
    with st.expander("Last query details"):
        last = st.session_state["history"][-1]
        st.write("**Question:**", last["question"])
        st.write("**Error:**", last["error"] or "None")
        st.code(last["raw_sql"] or "", language="sql")
        st.code(last["executed_sql"] or "", language="sql")
