
from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "sales_pipeline.csv"
MODEL_PATH = BASE_DIR / "deal_outcome_model.joblib"

CATEGORICAL_FEATURES = ["sales_agent", "product", "account"]
NUMERIC_FEATURES = [
    "engage_year",
    "engage_month",
    "engage_day_of_week",
]

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def load_data():
    df = pd.read_csv(DATA_PATH)

    # Only completed deals with genuine Won/Lost labels.
    df["deal_stage"] = df["deal_stage"].astype(str).str.strip().str.lower()
    df = df[df["deal_stage"].isin(["won", "lost"])].copy()

    df["engage_date"] = pd.to_datetime(
        df["engage_date"], errors="coerce"
    )

    # A chronological evaluation requires a known engagement date.
    df = df.dropna(subset=["engage_date"]).copy()

    # These are known at engagement time; closing information is excluded.
    df["engage_year"] = df["engage_date"].dt.year
    df["engage_month"] = df["engage_date"].dt.month
    df["engage_day_of_week"] = df["engage_date"].dt.dayofweek

    df["target"] = (df["deal_stage"] == "won").astype(int)

    # Normalize missing categories so preprocessing is predictable.
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].fillna("Unknown").astype(str)

    df = df.sort_values("engage_date").reset_index(drop=True)

    return df


def make_pipeline(model):
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        (
            "onehot",
            OneHotEncoder(handle_unknown="ignore"),
        ),
    ])

    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    preprocessing = ColumnTransformer([
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
    ])

    return Pipeline([
        ("preprocessing", preprocessing),
        ("model", model),
    ])


def evaluate(name, pipeline, X_train, y_train, X_test, y_test):
    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)
    probabilities = pipeline.predict_proba(X_test)[:, 1]

    print(f"\n{'=' * 55}")
    print(name)
    print("=" * 55)
    print(f"Accuracy:          {accuracy_score(y_test, predictions):.3f}")
    print(
        "Balanced accuracy: "
        f"{balanced_accuracy_score(y_test, predictions):.3f}"
    )
    print(f"F1 score (Won):    {f1_score(y_test, predictions):.3f}")

    if len(set(y_test)) == 2:
        print(f"ROC-AUC:           {roc_auc_score(y_test, probabilities):.3f}")

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

    print("Confusion matrix (rows=actual, columns=predicted):")
    print(confusion_matrix(y_test, predictions, labels=[0, 1]))

    return {
        "pipeline": pipeline,
        "balanced_accuracy": balanced_accuracy_score(y_test, predictions),
        "f1_won": f1_score(y_test, predictions),
    }


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = load_data()

    print("DEALPILOT AI — MODEL TRAINING")
    print(f"Dataset: {DATA_PATH}")
    print(f"Usable closed deals: {len(df)}")
    print(f"Won:  {int(df['target'].sum())}")
    print(f"Lost: {int((df['target'] == 0).sum())}")
    print(f"Date range: {df['engage_date'].min()} to {df['engage_date'].max()}")
    print("\nFeatures:", FEATURES)
    print("Excluded from features: opportunity_id, deal_stage, close_date, close_value")

    # Keep later opportunities unseen during evaluation.
    split_index = int(len(df) * 0.80)

    if split_index <= 0 or split_index >= len(df):
        raise ValueError("Not enough records for a chronological split.")

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    X_train = train_df[FEATURES]
    y_train = train_df["target"]
    X_test = test_df[FEATURES]
    y_test = test_df["target"]

    print(f"\nTraining rows: {len(train_df)}")
    print(f"Test rows:     {len(test_df)}")
    print(f"Test starts:   {test_df['engage_date'].min()}")

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError(
            "The chronological split must contain both Won and Lost "
            "outcomes in training and testing."
        )

    candidates = {
        "Logistic Regression": make_pipeline(
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
                random_state=42,
            )
        ),
        "Random Forest": make_pipeline(
            RandomForestClassifier(
                n_estimators=300,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
        ),
    }

    results = {}

    for name, pipeline in candidates.items():
        results[name] = evaluate(
            name, pipeline, X_train, y_train, X_test, y_test
        )

    # Select by chronological-test balanced accuracy, then Won F1.
    best_name = max(
        results,
        key=lambda name: (
            results[name]["balanced_accuracy"],
            results[name]["f1_won"],
        ),
    )

    print(f"\nSelected model: {best_name}")
    print(
        "Selection is based on the held-out chronological test set; "
        "it does not guarantee future accuracy."
    )

    # Retrain the selected model on all available closed records
    # only after evaluation is complete.
    best_pipeline = results[best_name]["pipeline"]
    best_pipeline.fit(df[FEATURES], df["target"])

    bundle = {
        "pipeline": best_pipeline,
        "model_name": best_name,
        "features": FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "training_rows": len(df),
        "target_mapping": {"lost": 0, "won": 1},
        "evaluation": {
            "balanced_accuracy": float(
                results[best_name]["balanced_accuracy"]
            ),
            "f1_won": float(results[best_name]["f1_won"]),
        },
        "warning": (
            "Experimental model trained on a fictional CRM dataset. "
            "Test metrics are not a guarantee of real-world performance."
        ),
    }

    joblib.dump(bundle, MODEL_PATH)
    print(f"\nSaved trained model to: {MODEL_PATH}")
    print("Training complete.")


if __name__ == "__main__":
    main()
