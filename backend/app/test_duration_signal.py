
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

DATA_PATH = Path(__file__).resolve().parent / "sales_pipeline.csv"


def main():
    df = pd.read_csv(DATA_PATH)

    df["deal_stage"] = (
        df["deal_stage"].astype(str).str.strip().str.lower()
    )

    df = df[
        df["deal_stage"].isin(["won", "lost"])
    ].copy()

    df["engage_date"] = pd.to_datetime(
        df["engage_date"], errors="coerce"
    )
    df["close_date"] = pd.to_datetime(
        df["close_date"], errors="coerce"
    )

    df = df.dropna(
        subset=["engage_date", "close_date"]
    ).copy()

    df["days_to_close"] = (
        df["close_date"] - df["engage_date"]
    ).dt.days

    df["won"] = (df["deal_stage"] == "won").astype(int)

    X = df[["days_to_close"]]
    y = df["won"]

    # Diagnostic experiment only; not a production model.
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = DecisionTreeClassifier(
        max_depth=3,
        random_state=42,
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]

    print("DIAGNOSTIC ONLY — DO NOT USE FOR LIVE PREDICTIONS")
    print("Feature: days_to_close (known only after closing)")
    print(f"Test records: {len(y_test)}")
    print(f"Accuracy: {accuracy_score(y_test, predictions):.3f}")
    print(
        "Balanced accuracy: "
        f"{balanced_accuracy_score(y_test, predictions):.3f}"
    )
    print(f"ROC-AUC: {roc_auc_score(y_test, probabilities):.3f}")

    print("\nLearned decision rules:")
    from sklearn.tree import export_text
    print(export_text(model, feature_names=["days_to_close"]))


if __name__ == "__main__":
    main()
