# tests/test_prompt_builder.py
from app.prompt_builder import build_prompt

def test_prompt_includes_user_question():
    schema_mock = """
    ### Database Schema (SQLite)
    - **Artist**: ArtistId INTEGER, Name NVARCHAR(120)
    """
    q = "List all artists."
    prompt = build_prompt(q, schema_mock)

    assert q in prompt
    assert "Database Schema" in prompt
    assert "Examples" in prompt
    assert "Return only the SQL" in prompt

def test_prompt_has_rules():
    schema = "### Database Schema (SQLite)\n- **Artist**: ArtistId"
    prompt = build_prompt("Hello?", schema)

    assert "SELECT-only" in prompt or "Only return a single SQL" in prompt
    assert "explicit JOINs" in prompt
