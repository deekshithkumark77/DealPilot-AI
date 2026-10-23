
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / "sales_pipeline.csv"


def main():
    if not DATA_PATH.exists():
        print(f"Dataset not found: {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH)

    print("=" * 60)
    print("DEALPILOT AI — TRAINING DATA INSPECTION")
    print("=" * 60)

    print(f"\nRows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\n1. DEAL STAGE COUNTS")
    print(df["deal_stage"].value_counts(dropna=False).to_string())

    print("\n2. DEAL STAGE PERCENTAGES")
    print(
        (df["deal_stage"].value_counts(normalize=True) * 100)
        .round(2)
        .to_string()
    )

    print("\n3. WON / LOST COUNTS")
    normalized = df["deal_stage"].astype(str).str.strip().str.lower()
    print("Won:", int((normalized == "won").sum()))
    print("Lost:", int((normalized == "lost").sum()))
    print("Other stages:", int((~normalized.isin(["won", "lost"])).sum()))

    print("\n4. MISSING VALUES")
    print(df.isnull().sum().to_string())

    print("\n5. ENGAGEMENT DATE RANGE")
    dates = pd.to_datetime(df["engage_date"], errors="coerce")
    print("Earliest:", dates.min())
    print("Latest:", dates.max())

    print("\n6. SAMPLE RECORDS")
    print(df.head(10).to_string(index=False))

    print("\n7. DATA QUALITY CHECKS")
    print("Duplicate opportunity IDs:", df["opportunity_id"].duplicated().sum())
    print("Duplicate complete rows:", df.duplicated().sum())

    closed = df[normalized.isin(["won", "lost"])].copy()
    print("\n8. CLOSED DEALS")
    print("Closed records:", len(closed))
    print("Closed outcomes:")
    print(closed["deal_stage"].value_counts().to_string())

    print("\nInspection complete. No data was modified.")


if __name__ == "__main__":
    main()
