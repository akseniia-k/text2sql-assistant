import pytest
from app.sql_guard import guard_sql, SqlGuardError, NotSelectError, DangerousKeywordError, MultipleStatementsError

def test_select_passes_when_has_limit():
    sql = "SELECT Name FROM artists LIMIT 5;"
    out = guard_sql(sql)
    assert out.strip().lower().startswith("select")
    assert "limit" in out.lower()
    assert out.rstrip().endswith(";")

def test_select_adds_limit_when_missing():
    sql = "SELECT Name FROM artists"
    out = guard_sql(sql)
    assert "limit 1000" in out.lower()

def test_with_cte_is_allowed_and_gets_limit():
    sql = """
    WITH top_artists AS (
      SELECT ArtistId, COUNT(*) AS albums FROM albums GROUP BY ArtistId
    )
    SELECT * FROM top_artists ORDER BY albums DESC;
    """
    out = guard_sql(sql)
    assert out.lower().startswith("with")
    assert "limit" in out.lower()

def test_update_is_blocked():
    sql = "UPDATE artists SET Name='X' WHERE ArtistId=1;"
    with pytest.raises(DangerousKeywordError):
        guard_sql(sql)

def test_multiple_statements_are_blocked():
    sql = "SELECT 1; SELECT 2;"
    with pytest.raises(MultipleStatementsError):
        guard_sql(sql)

def test_comments_are_ignored_in_checks():
    sql = """
    -- harmless comment
    SELECT Name FROM artists /* block comment */ WHERE Name LIKE 'A%';
    """
    out = guard_sql(sql)
    assert "limit" in out.lower()

def test_not_select_is_blocked():
    sql = "PRAGMA table_info(artists);"
    with pytest.raises(SqlGuardError):
        guard_sql(sql)

def test_spacing_and_semicolon_handling():
    sql = "  select  Name   from   artists  "
    out = guard_sql(sql)
    # normalized spacing and limit appended
    assert "select name from artists" in out.lower()
    assert out.lower().endswith(";") or "limit" in out.lower()
