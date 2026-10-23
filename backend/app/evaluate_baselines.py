
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.dummy import DummyClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

DATA_PATH = Path(__file__).resolve().parent / "sales_pipeline.csv"


def main():
    df = pd.read_csv(DATA_PATH)

    df["deal_stage"] = df["deal_stage"].astype(str).str.strip().str.lower()
    df = df[df["deal_stage"].isin(["won", "lost"])].copy()

    df["engage_date"] = pd.to_datetime(df["engage_date"], errors="coerce")
    df = df.dropna(subset=["engage_date"]).copy()

    df["engage_year"] = df["engage_date"].dt.year
    df["engage_month"] = df["engage_date"].dt.month

    df["target"] = (df["deal_stage"] == "won").astype(int)
    df["account"] = df["account"].fillna("Unknown")
    df = df.sort_values("engage_date").reset_index(drop=True)

    features = ["sales_agent", "product", "account", "engage_year", "engage_month"]
    X = df[features]
    y = df["target"]

    split = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # Baseline: always predict the most common outcome in training data.
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train, y_train)

    # Baseline: logistic regression using the same candidate features.
    categorical = ["sales_agent", "product", "account"]
    numeric = ["engage_year", "engage_month"]

    preprocess = ColumnTransformer([
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]), categorical),
        ("num", SimpleImputer(strategy="median"), numeric),
    ])

    logistic = Pipeline([
        ("preprocess", preprocess),
        ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])
    logistic.fit(X_train, y_train)

    print("Held-out chronological test set:", len(y_test), "rows")
    print("Actual test outcomes:", y_test.value_counts().to_dict())

    for name, model in [
        ("Majority-class baseline", dummy),
        ("Logistic Regression", logistic),
    ]:
        pred = model.predict(X_test)
        print(f"\n{name}")
        print("Accuracy:", round(accuracy_score(y_test, pred), 3))
        print("Balanced accuracy:", round(balanced_accuracy_score(y_test, pred), 3))
        print("Won F1:", round(f1_score(y_test, pred, zero_division=0), 3))

        if hasattr(model, "predict_proba") and y_test.nunique() == 2:
            prob = model.predict_proba(X_test)[:, 1]
            print("ROC-AUC:", round(roc_auc_score(y_test, prob), 3))


if __name__ == "__main__":
    main()
