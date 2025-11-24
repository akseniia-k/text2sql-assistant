# tests/test_schema_reader.py
from app.schema_reader import get_schema_text, read_schema
from sqlalchemy import create_engine

def test_schema_text_contains_known_table():
    engine = create_engine("sqlite:///data/chinook.sqlite")
    schema = read_schema(engine, max_tables=50, max_cols_per_table=50)

    # Make sure at least one of the expected Chinook tables is detected
    tables = schema["tables"].keys()
    assert len(tables) > 0, "No tables found in schema."

    # Check for common tables (CamelCase version)
    expected = {"Artist", "Album", "Track", "Invoice", "InvoiceLine", "Customer"}
    assert any(t in tables for t in expected), f"None of the expected tables found. Got: {tables}"

def test_get_schema_text_returns_string():
    text = get_schema_text("data/chinook.sqlite", sample_rows_per_table=0)
    assert isinstance(text, str)
    assert "### Database Schema" in text
