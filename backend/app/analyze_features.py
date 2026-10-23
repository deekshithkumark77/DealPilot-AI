
from pathlib import Path
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / "sales_pipeline.csv"


def main():
    df = pd.read_csv(DATA_PATH)

    df["deal_stage"] = (
        df["deal_stage"].astype(str).str.strip().str.lower()
    )

    df["engage_date"] = pd.to_datetime(
        df["engage_date"], errors="coerce"
    )
    df["close_date"] = pd.to_datetime(
        df["close_date"], errors="coerce"
    )

    # Only completed deals for outcome analysis.
    closed = df[
        df["deal_stage"].isin(["won", "lost"])
    ].copy()

    closed["won"] = (
        closed["deal_stage"] == "won"
    ).astype(int)

    print("\n1. CLOSED DEALS BY ENGAGEMENT YEAR AND OUTCOME")

    closed["engage_year"] = closed["engage_date"].dt.year

    print(
        pd.crosstab(
            closed["engage_year"],
            closed["deal_stage"],
            margins=True
        ).to_string()
    )

    print("\n2. WIN RATE BY ENGAGEMENT YEAR")

    print(
        closed.dropna(subset=["engage_year"])
        .groupby("engage_year")["won"]
        .agg(
            closed_deals="size",
            wins="sum",
            win_rate="mean"
        )
        .assign(
            win_rate=lambda x: (
                x["win_rate"] * 100
            ).round(1)
        )
        .to_string()
    )

    print("\n3. TIME BETWEEN ENGAGEMENT AND CLOSING")

    timed = closed.dropna(
        subset=["engage_date", "close_date"]
    ).copy()

    timed["days_to_close"] = (
        timed["close_date"] - timed["engage_date"]
    ).dt.days

    print(
        timed["days_to_close"]
        .describe(percentiles=[0.25, 0.5, 0.75])
        .round(1)
        .to_string()
    )

    print("\n4. CLOSING TIME BY OUTCOME")

    print(
        timed.groupby("deal_stage")["days_to_close"]
        .agg(["count", "median", "mean"])
        .round(1)
        .to_string()
    )

    print("\n5. MISSING DATA IN ORIGINAL DATASET")

    print(
        df.isna().sum()
        .sort_values(ascending=False)
        .to_string()
    )

    print("\n6. PRODUCT AND OUTCOME COUNTS")

    print(
        pd.crosstab(
            closed["product"],
            closed["deal_stage"],
            margins=True
        ).to_string()
    )


if __name__ == "__main__":
    main()
