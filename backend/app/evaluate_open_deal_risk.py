
from pathlib import Path

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "sales_pipeline.csv"

CATEGORICAL_FEATURES = [
    "sales_agent",
    "product",
    "account",
]

NUMERIC_FEATURES = [
    "engage_year",
    "engage_month",
    "engage_day_of_week",
]

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def load_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    df = pd.read_csv(DATA_PATH)

    df["deal_stage"] = (
        df["deal_stage"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # Learn outcomes only from genuinely completed deals.
    df = df[
        df["deal_stage"].isin(["won", "lost"])
    ].copy()

    df["engage_date"] = pd.to_datetime(
        df["engage_date"],
        errors="coerce",
    )

    # A chronological evaluation needs a known engagement date.
    df = df.dropna(
        subset=["engage_date"]
    ).copy()

    df["engage_year"] = (
        df["engage_date"].dt.year
    )
    df["engage_month"] = (
        df["engage_date"].dt.month
    )
    df["engage_day_of_week"] = (
        df["engage_date"].dt.dayofweek
    )

    # 1 = eventually Won; 0 = eventually Lost.
    # The target is never included in FEATURES.
    df["target"] = (
        df["deal_stage"] == "won"
    ).astype(int)

    for column in CATEGORICAL_FEATURES:
        df[column] = (
            df[column]
            .fillna("Unknown")
            .astype(str)
        )

    # Stable ordering for a chronological holdout.
    df = (
        df.sort_values("engage_date")
        .reset_index(drop=True)
    )

    return df


def make_model(classifier):
    categorical_pipeline = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="most_frequent"),
        ),
        (
            "onehot",
            OneHotEncoder(handle_unknown="ignore"),
        ),
    ])

    numeric_pipeline = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
        ("scaler", StandardScaler()),
    ])

    preprocessing = ColumnTransformer([
        (
            "categorical",
            categorical_pipeline,
            CATEGORICAL_FEATURES,
        ),
        (
            "numeric",
            numeric_pipeline,
            NUMERIC_FEATURES,
        ),
    ])

    return Pipeline([
        ("preprocessing", preprocessing),
        ("model", classifier),
    ])


def report_results(name, model, X_test, y_test):
    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]

    print(f"\n{'=' * 55}")
    print(name)
    print("=" * 55)

    print(
        f"Accuracy:          "
        f"{accuracy_score(y_test, predictions):.3f}"
    )

    print(
        f"Balanced accuracy: "
        f"{balanced_accuracy_score(y_test, predictions):.3f}"
    )

    print(
        f"ROC-AUC:           "
        f"{roc_auc_score(y_test, probabilities):.3f}"
    )

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["Lost", "Won"],
            zero_division=0,
        )
    )

    print(
        "Confusion matrix "
        "(rows=actual Lost/Won, columns=predicted Lost/Won):"
    )

    print(
        confusion_matrix(
            y_test,
            predictions,
            labels=[0, 1],
        )
    )


def main():
    df = load_data()

    print("DEALPILOT AI — OPEN DEAL RISK EVALUATION")
    print("-" * 55)
    print(f"Completed deals with engagement dates: {len(df)}")
    print(f"Lost deals: {(df['target'] == 0).sum()}")
    print(f"Won deals:  {(df['target'] == 1).sum()}")
    print(f"Date range: {df['engage_date'].min()} to "
          f"{df['engage_date'].max()}")

    print("\nFeatures used:")
    for feature in FEATURES:
        print(f" - {feature}")

    print("\nExcluded outcome/future fields:")
    print(" - deal_stage (used only to create the target)")
    print(" - close_date")
    print(" - close_value")
    print(" - days_to_close")

    # Reserve the latest 20% of records for testing.
    split_index = int(len(df) * 0.80)

    if split_index <= 0 or split_index >= len(df):
        raise ValueError(
            "Not enough records for a chronological split."
        )

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    X_train = train_df[FEATURES]
    y_train = train_df["target"]

    X_test = test_df[FEATURES]
    y_test = test_df["target"]

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError(
            "Both train and test sets must contain Won and Lost."
        )

    print(f"\nTraining records: {len(train_df)}")
    print(f"Testing records:  {len(test_df)}")
    print(
        "Test period starts: "
        f"{test_df['engage_date'].min()}"
    )

    # Baseline: always predict the most common training outcome.
    baseline = DummyClassifier(
        strategy="most_frequent"
    )
    baseline.fit(X_train, y_train)

    report_results(
        "MAJORITY-CLASS BASELINE",
        baseline,
        X_test,
        y_test,
    )

    # Actual ML model.
    model = make_model(
        LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=42,
        )
    )

    model.fit(X_train, y_train)

    report_results(
        "LOGISTIC REGRESSION — PRE-CLOSURE FEATURES",
        model,
        X_test,
        y_test,
    )

    print("\n" + "=" * 55)
    print("EVALUATION COMPLETE")
    print("=" * 55)
    print(
        "This is a retrospective outcome experiment, not proof "
        "of reliable live open-deal risk prediction."
    )
    print(
        "The dataset lacks historical snapshots of open deals "
        "and their features at specific prediction times."
    )


if __name__ == "__main__":
    main()
