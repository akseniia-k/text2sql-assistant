🚀 Text-to-SQL Assistant

A natural-language interface for querying relational databases using LLM-generated SQL.

📖 Overview

Text-to-SQL Assistant lets users ask questions in natural language and automatically converts them into safe, validated SQLite SQL queries, returning results instantly.

It aims to democratize access to data by enabling non-technical stakeholders to query databases without writing SQL. The assistant exposes SQL generation, validation, schema interpretation, and execution in a clean and transparent UI.

This project is designed as a portfolio-ready, end-to-end data engineering + LLM system, with safe SQL generation, schema-aware prompting, evaluation, and a Streamlit interface.

🌟 Features
✔️ Natural language → SQL

Uses an LLM (OpenAI gpt-4o-mini by default) to translate English questions into SQL SELECT statements.

✔️ Automatic schema ingestion

Reads any SQLite database using SQLAlchemy reflection and injects the schema into the LLM prompt.

✔️ SQL guardrails (safety)

Prevents dangerous operations like UPDATE, DELETE, DROP, and enforces:

SELECT-only

LIMIT added automatically

Single-statement queries

Case-sensitive table/column names

✔️ Debug visibility

The UI shows:

Generated SQL

Executed SQL (after guard)

Full prompt

Parsed schema

✔️ Streamlit UI

Interactive, clean, and responsive:

Query input

On-the-fly results

Downloadable CSV

Expanders for schema & prompt

🧠 How It Works
question → schema_reader → prompt_builder → LLM
        → sql_guard → db_executor → results (+ CSV)
                        ↘ eval logger

1. Schema Reader

Reads tables, columns, PK/FK relationships using SQLAlchemy reflection.

2. Prompt Builder

Creates a structured system prompt:

Rules for SQLite

Schema summary

Few-shot examples

User question

3. LLM Client

Calls OpenAI’s Chat Completions API with clean, deterministic settings (T=0).

4. SQL Guard

Validates and sanitizes LLM-generated SQL.

5. Executor

Runs the final SQL safely and returns results via Pandas.

6. Streamlit UI

Displays results, SQL, schema, and debugging info.

🖥️ Example Query

Below is a fully generated SQL pipeline example.

The assistant responds with both:

Generated SQL

Executed SQL (after safety guardrail modifications)

Tabular results

🧱 Database Schema View

The app exposes a transparent, LLM-ready database schema.

🧩 Full Prompt (Debug)

You can see the exact prompt given to the LLM for reproducibility and debugging.
This includes rules, schema, and few-shot examples.

📦 Project Structure
text2sql-assistant/
├─ app/
│  ├─ schema_reader.py       # Auto-ingest DB schema
│  ├─ prompt_builder.py      # System prompt + few-shot examples
│  ├─ llm_client.py          # OpenAI client wrapper
│  ├─ sql_guard.py           # SELECT-only & safety
│  ├─ db.py                  # SQLite execution utils
│  ├─ orchestrator.py        # CLI pipeline
│  ├─ ui_streamlit.py        # Streamlit UI
├─ data/
│  └─ chinook.sqlite         # Example database
├─ evaluation/
│  ├─ qa_pairs.jsonl         # Gold labeled test set
│  └─ run_eval.py            # Execution & exact-match metrics
├─ tests/
│  ├─ test_schema_reader.py
│  ├─ test_sql_guard.py
│  ├─ test_prompt_builder.py
│  └─ test_pipeline.py
└─ images/
   ├─ ui_main.png
   ├─ query_example.png
   ├─ schema_view.png
   ├─ full_prompt.png
   └─ settings_sidebar.png

⚙️ Installation & Setup
1. Clone the repo
git clone https://github.com/akseniia-k/text2sql-assistant.git
cd text2sql-assistant

2. Create environment
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

3. Add OpenAI API Key

Create a .env file in the project root:

OPENAI_API_KEY=your_key_here

4. Run the UI
streamlit run app/ui_streamlit.py

📊 Evaluation

You can measure:

Execution success rate

Exact SQL match

Result equivalence

Run:

python -m evaluation.run_eval --validate evaluation/qa_pairs.jsonl --sanity --db data/chinook.sqlite

🔒 SQL Safety

This project includes a hardened guardrail system:

Denylist (UPDATE, DELETE, INSERT, ALTER, DROP, …)

SELECT-only validation

Automatic LIMIT

Single-statement enforcement

If SQL is rejected, the model is asked to repair it via a secondary LLM prompt.

🎯 Project Goals

This project demonstrates real-world abilities in:

✔️ LLM-powered data systems
✔️ Prompt engineering
✔️ SQL query generation & safety
✔️ Streamlit UI development
✔️ Testing & evaluation pipelines
✔️ Clean architecture & modular Python design
🧭 Future Enhancements

Fine-tuned model using synthetic Text-to-SQL data

Support for Postgres & MySQL

User authentication

Query history persistence

Role-based query restrictions

👩‍💻 Author

Akseniia K.
Data Science & AI Engineer
LinkedIn: https://www.linkedin.com/in/akseniia-k/