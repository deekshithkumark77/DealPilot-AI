
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "dealpilot.db"


def main():
    print(f"Database path: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database file not found. No changes were made.")
        return

    with sqlite3.connect(DB_PATH) as connection:
        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        print("\nDATABASE TABLES")

        for (table_name,) in tables:
            print(f"\n--- {table_name} ---")

            # Table names come from this database's own metadata.
            escaped_name = table_name.replace('"', '""')

            columns = connection.execute(
                f'PRAGMA table_info("{escaped_name}")'
            ).fetchall()

            for column in columns:
                _, name, data_type, not_null, default, primary_key = column
                print(
                    f"{name}: {data_type or 'UNKNOWN'}"
                    f"{' (PRIMARY KEY)' if primary_key else ''}"
                )

            count = connection.execute(
                f'SELECT COUNT(*) FROM "{escaped_name}"'
            ).fetchone()[0]

            print(f"Row count: {count}")


if __name__ == "__main__":
    main()
