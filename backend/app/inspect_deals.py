
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "dealpilot.db"


def main():
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        print("TOTAL DEALS")
        print(
            connection.execute(
                "SELECT COUNT(*) FROM deals"
            ).fetchone()[0]
        )

        print("\nALL DEAL RECORDS")
        rows = connection.execute("""
            SELECT
                id,
                title,
                status,
                customer_id,
                product_id,
                quantity,
                proposed_unit_price,
                expected_close_date,
                created_at
            FROM deals
            ORDER BY id
        """).fetchall()

        for row in rows:
            print("-" * 50)
            for key in row.keys():
                print(f"{key}: {row[key]}")

        print("\nSTATUS COUNTS")
        for row in connection.execute("""
            SELECT status, COUNT(*) AS total
            FROM deals
            GROUP BY status
            ORDER BY status
        """):
            print(f"{row['status']}: {row['total']}")


if __name__ == "__main__":
    main()
