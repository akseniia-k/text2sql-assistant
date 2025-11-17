"""
Builds the full prompt that the LLM sees:
system rules → schema → few-shot examples → user question.
"""

from textwrap import dedent

# ----------------------------
# 1️SYSTEM PROMPT (rules)
# ----------------------------

SYSTEM_RULES = dedent("""
You are an expert SQL generator.

Follow these strict rules:
- Dialect: **SQLite**
- Only return a single SQL SELECT statement.
- Use ONLY the tables and columns listed in the schema below.
- Always use explicit JOINs (no implicit joins).
- Fully qualify columns (e.g., artists.Name).
- Never modify, create, or delete data (no INSERT/UPDATE/DELETE/ALTER).
- If no LIMIT is specified, append LIMIT 1000.
- Return **only** the SQL — no explanations, no markdown, no code fences.
""").strip()


# ----------------------------
# 2️FEW-SHOT EXAMPLES
# ----------------------------

def build_few_shots() -> str:
    """Provide 4–6 progressive text→SQL examples for the model."""
    examples = [
        {
            "question": "List the first 5 artist names.",
            "sql": "SELECT Name FROM artists ORDER BY Name LIMIT 5;"
        },
        {
            "question": "Show each album with its artist name.",
            "sql": (
                "SELECT albums.Title AS AlbumTitle, artists.Name AS ArtistName "
                "FROM albums "
                "JOIN artists ON albums.ArtistId = artists.ArtistId "
                "LIMIT 5;"
            )
        },
        {
            "question": "Find the number of albums per artist (top 10).",
            "sql": (
                "SELECT artists.Name, COUNT(albums.AlbumId) AS AlbumCount "
                "FROM artists "
                "JOIN albums ON artists.ArtistId = albums.ArtistId "
                "GROUP BY artists.Name "
                "ORDER BY AlbumCount DESC "
                "LIMIT 10;"
            )
        },
        {
            "question": "List the top 5 genres by total number of tracks.",
            "sql": (
                "SELECT genres.Name AS Genre, COUNT(tracks.TrackId) AS TrackCount "
                "FROM genres "
                "JOIN tracks ON genres.GenreId = tracks.GenreId "
                "GROUP BY genres.Name "
                "ORDER BY TrackCount DESC "
                "LIMIT 5;"
            )
        },
        {
            "question": "Find total sales in 2010.",
            "sql": (
                "SELECT SUM(InvoiceTotal) AS TotalSales "
                "FROM ( "
                "SELECT invoices.Total AS InvoiceTotal "
                "FROM invoices "
                "WHERE strftime('%Y', invoices.InvoiceDate) = '2010' "
                ");"
            )
        },
        {
            "question": "Show the top 10 customers by total spend.",
            "sql": (
                "SELECT customers.FirstName || ' ' || customers.LastName AS Customer, "
                "SUM(invoice_items.Quantity * invoice_items.UnitPrice) AS TotalSpent "
                "FROM customers "
                "JOIN invoices ON customers.CustomerId = invoices.CustomerId "
                "JOIN invoice_items ON invoices.InvoiceId = invoice_items.InvoiceId "
                "GROUP BY customers.CustomerId "
                "ORDER BY TotalSpent DESC "
                "LIMIT 10;"
            )
        },
    ]

    # format examples nicely
    lines = ["### Examples"]
    for ex in examples:
        lines.append(f"\nUser: {ex['question']}\nSQL: {ex['sql']}")
    return "\n".join(lines)


# ----------------------------
# 3️BUILD THE FINAL PROMPT
# ----------------------------

def build_prompt(user_question: str, schema_text: str) -> str:
    """
    Combine system rules, schema markdown, few-shot examples,
    and the user's current question into one final prompt string.
    """
    few_shots = build_few_shots()

    prompt = dedent(f"""
    {SYSTEM_RULES}

    {schema_text}

    {few_shots}

    ### User question
    {user_question}

    Return only the SQL query.
    """).strip()

    return prompt


# ----------------------------
# 4️CLI TEST
# ----------------------------

if __name__ == "__main__":
    from app.schema_reader import get_schema_text
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m app.prompt_builder <db_path> \"<question>\"")
        sys.exit(1)

    db_path = sys.argv[1]
    question = sys.argv[2]

    schema_text = get_schema_text(db_path, sample_rows_per_table=1)
    full_prompt = build_prompt(question, schema_text)
    print(full_prompt)
