
"""Machine-learning service for DealPilot AI.

Trains a Logistic Regression model using recorded won/lost deals.
Open deals are never treated as labelled training outcomes.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from . import models


MODEL_PATH = Path(__file__).resolve().parent / "deal_outcome_model.joblib"

FEATURE_NAMES = [
    "log_quantity",
    "log_deal_value",
    "price_vs_list",
    "gross_margin_rate",
    "days_to_close",
    "close_date_missing",
    "notes_positive_signal",
    "notes_risk_signal",
]

POSITIVE_TERMS = (
    "budget approved",
    "ready to sign",
    "purchase order",
    "confirmed",
    "approved budget",
    "renewal confirmed",
)

RISK_TERMS = (
    "no response",
    "not responding",
    "competitor",
    "budget issue",
    "price objection",
    "delayed",
    "cancel",
    "too expensive",
    "postponed",
)


def extract_features(deal, product=None):
    """Convert a deal into numeric features for the model."""

    quantity = max(float(deal.quantity or 0), 0)
    price = max(float(deal.proposed_unit_price or 0), 0)
    deal_value = quantity * price

    list_price = float(product.list_price or 0) if product else 0
    unit_cost = float(product.unit_cost or 0) if product else 0

    price_vs_list = (
        price / list_price if list_price > 0 else 1.0
    )

    gross_margin_rate = (
        (price - unit_cost) / price
        if price > 0 and product
        else 0.0
    )

    raw_date = (deal.expected_close_date or "").strip()
    close_date_missing = 1.0
    days_to_close = 0.0

    if raw_date:
        try:
            close_date = date.fromisoformat(raw_date[:10])
            days_to_close = float(
                (close_date - date.today()).days
            )
            close_date_missing = 0.0
        except ValueError:
            pass

    notes = (deal.notes or "").lower()

    has_positive_signal = float(
        any(term in notes for term in POSITIVE_TERMS)
    )

    has_risk_signal = float(
        any(term in notes for term in RISK_TERMS)
    )

    return [
        math.log1p(quantity),
        math.log1p(deal_value),
        price_vs_list,
        gross_margin_rate,
        days_to_close,
        close_date_missing,
        has_positive_signal,
        has_risk_signal,
    ]


def get_model_status(db: Session):
    """Report whether a trained model exists and the available data."""

    records = (
        db.query(models.Deal)
        .filter(models.Deal.status.in_(["won", "lost"]))
        .all()
    )

    won_count = sum(deal.status == "won" for deal in records)
    lost_count = sum(deal.status == "lost" for deal in records)

    model_ready = MODEL_PATH.exists()

    if model_ready:
        message = (
            "A trained model file exists. Retrain it after "
            "adding or changing historical outcomes."
        )
    else:
        message = (
            "No trained model exists yet. Training requires at least "
            "12 historical won/lost deals, including at least 4 won "
            "and 4 lost deals."
        )

    return {
        "model_type": "LogisticRegression",
        "model_ready": model_ready,
        "training_rows": len(records),
        "won_rows": won_count,
        "lost_rows": lost_count,
        "minimum_rows": 12,
        "minimum_per_class": 4,
        "message": message,
    }


def train_model(db: Session):
    """Train and save a model using historical won/lost deals."""

    records = (
        db.query(models.Deal)
        .filter(models.Deal.status.in_(["won", "lost"]))
        .all()
    )

    y = np.array(
        [1 if deal.status == "won" else 0 for deal in records],
        dtype=int,
    )

    won_count = int(y.sum())
    lost_count = int((y == 0).sum())

    if len(records) < 12 or min(won_count, lost_count) < 4:
        return {
            "trained": False,
            "status": get_model_status(db),
            "error": (
                "Not enough labelled historical data. Add genuine "
                "won and lost outcomes before training. Open deals "
                "must not be used as training labels."
            ),
        }

    X = np.array(
        [
            extract_features(deal, deal.product)
            for deal in records
        ],
        dtype=float,
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    # Evaluate on held-out records before fitting the final model.
    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)
    probabilities = pipeline.predict_proba(X_test)[:, 1]

    metrics = {
        "holdout_rows": int(len(y_test)),
        "accuracy": round(
            float(accuracy_score(y_test, predictions)), 3
        ),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(y_test, predictions)), 3
        ),
    }

    if len(set(y_test.tolist())) == 2:
        metrics["roc_auc"] = round(
            float(roc_auc_score(y_test, probabilities)), 3
        )

    # Refit the final model on all available labelled records.
    pipeline.fit(X, y)

    joblib.dump(
        {
            "pipeline": pipeline,
            "features": FEATURE_NAMES,
            "training_rows": len(records),
            "won_rows": won_count,
            "lost_rows": lost_count,
        },
        MODEL_PATH,
    )

    return {
        "trained": True,
        "model_type": "LogisticRegression",
        "training_rows": len(records),
        "won_rows": won_count,
        "lost_rows": lost_count,
        "holdout_metrics": metrics,
        "warning": (
            "Small or synthetic datasets can produce unstable metrics. "
            "These metrics do not establish production accuracy."
        ),
    }


def predict_deal(db: Session, deal_id: int):
    """Predict a deal outcome using the saved trained model."""

    deal = db.get(models.Deal, deal_id)

    if not deal:
        return None

    if not MODEL_PATH.exists():
        return {
            "available": False,
            "error": (
                "No trained ML model exists. Training requires at least "
                "12 labelled won/lost deals, with at least 4 in each class."
            ),
        }

    bundle = joblib.load(MODEL_PATH)

    pipeline = bundle["pipeline"]

    X = np.array(
        [extract_features(deal, deal.product)],
        dtype=float,
    )

    win_score = float(pipeline.predict_proba(X)[0][1])

    return {
        "available": True,
        "deal_id": deal.id,
        "deal_title": deal.title,
        "model_type": "LogisticRegression",
        "predicted_outcome": "won" if win_score >= 0.5 else "lost",
        "win_score_percent": round(win_score * 100, 1),
        "loss_score_percent": round((1 - win_score) * 100, 1),
        "threshold": 50,
        "training_rows": bundle["training_rows"],
        "features_used": FEATURE_NAMES,
        "disclaimer": (
            "Experimental model scores, not calibrated probabilities "
            "or guarantees. Validate using more real historical outcomes."
        ),
    }
