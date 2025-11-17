import argparse
from sqlalchemy import create_engine, inspect

def main():
    parser = argparse.ArgumentParser(description="List tables from a SQLite DB using SQLAlchemy.")
    parser.add_argument("db_path", help="Path to the SQLite file, e.g. data/chinook.sqlite")
    args = parser.parse_args()

    uri = args.db_path if args.db_path.startswith("sqlite:///") else f"sqlite:///{args.db_path}"
    engine = create_engine(uri)
    insp = inspect(engine)
    tables = insp.get_table_names()

    if not tables:
        print("No tables found. Is this a valid SQLite DB?")
        return

    print("✅ Connection OK. Found tables:")
    for t in tables:
        print(f" - {t}")

if __name__ == "__main__":
    main()
