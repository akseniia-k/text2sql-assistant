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
- Table and column names are **case-sensitive**; use them exactly as shown in the schema.
- Use ONLY the tables and columns listed in the schema below.
- Always use explicit JOINs (no implicit joins).
- Fully qualify columns (e.g., Artist.Name).
- Never modify, create, or delete data (no INSERT/UPDATE/DELETE/ALTER).
- If no LIMIT is specified, append LIMIT 1000.
- Return **only** the SQL — no explanations, no markdown, no code fences.
""").strip()


# ----------------------------
# 2️FEW-SHOT EXAMPLES
# ----------------------------

def build_few_shots() -> str:
    """Provide 4–6 progressive text→SQL examples for the model (Chinook, CamelCase tables)."""
    examples = [
        # 1) Single table select
        {
            "question": "List the first 5 artist names.",
            "sql": "SELECT Name FROM Artist ORDER BY Name ASC LIMIT 5;"
        },
        # 2) Simple join (Artist ↔ Album)
        {
            "question": "Show each album with its artist name (first 5).",
            "sql": (
                "SELECT Album.Title AS AlbumTitle, Artist.Name AS ArtistName "
                "FROM Album "
                "JOIN Artist ON Album.ArtistId = Artist.ArtistId "
                "ORDER BY Album.Title ASC "
                "LIMIT 5;"
            )
        },
        # 3) Aggregation + GROUP BY (albums per artist)
        {
            "question": "How many albums does each artist have? Return top 10 by album count.",
            "sql": (
                "SELECT Artist.Name AS Artist, COUNT(Album.AlbumId) AS AlbumCount "
                "FROM Artist "
                "JOIN Album ON Artist.ArtistId = Album.ArtistId "
                "GROUP BY Artist.Name "
                "ORDER BY AlbumCount DESC, Artist ASC "
                "LIMIT 10;"
            )
        },
        # 4) Top-N with ORDER BY/LIMIT (genres by track count)
        {
            "question": "Top 5 genres by number of tracks.",
            "sql": (
                "SELECT Genre.Name AS Genre, COUNT(Track.TrackId) AS TrackCount "
                "FROM Genre "
                "JOIN Track ON Genre.GenreId = Track.GenreId "
                "GROUP BY Genre.Name "
                "ORDER BY TrackCount DESC, Genre ASC "
                "LIMIT 5;"
            )
        },
        # 5) Date filter using Invoice
        {
            "question": "Total sales amount in 2010.",
            "sql": (
                "SELECT SUM(Invoice.Total) AS TotalSales "
                "FROM Invoice "
                "WHERE strftime('%Y', Invoice.InvoiceDate) = '2010';"
            )
        },
        # 6) Multi-join (Customer ↔ Invoice ↔ InvoiceLine ↔ Track)
        {
            "question": "Show the top 10 customers by total spend.",
            "sql": (
                "SELECT Customer.CustomerId, "
                "Customer.FirstName || ' ' || Customer.LastName AS Customer, "
                "SUM(InvoiceLine.Quantity * InvoiceLine.UnitPrice) AS TotalSpent "
                "FROM Customer "
                "JOIN Invoice ON Customer.CustomerId = Invoice.CustomerId "
                "JOIN InvoiceLine ON Invoice.InvoiceId = InvoiceLine.InvoiceId "
                "GROUP BY Customer.CustomerId "
                "ORDER BY TotalSpent DESC, Customer ASC "
                "LIMIT 10;"
            )
        },
    ]

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
