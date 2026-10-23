
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

DATA = Path(
    "ai/component2-behavioral/data/processed/depth/depth_dataset.npz"
)
OUTPUT = Path("ai/component2-behavioral/data/processed/results")
OUTPUT.mkdir(parents=True, exist_ok=True)

with np.load(DATA, allow_pickle=False) as data:
    X = data["X"]
    y = data["y"]
    groups = data["sequences"]

# Keep all frames from a sequence in the same split.
splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.25,
    random_state=42,
)

train_idx, test_idx = next(
    splitter.split(X, y, groups=groups)
)

X_train, X_test = X[train_idx], X[test_idx]
y_train, y_test = y[train_idx], y[test_idx]

print("Total samples:", len(y))
print("Train samples:", len(train_idx))
print("Test samples:", len(test_idx))
print("Train sequences:", len(np.unique(groups[train_idx])))
print("Test sequences:", len(np.unique(groups[test_idx])))
print("Train class counts:", np.bincount(y_train, minlength=2))
print("Test class counts:", np.bincount(y_test, minlength=2))

models = {
    "Logistic Regression": make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        ),
    ),
    "Random Forest": make_pipeline(
        SimpleImputer(strategy="median"),
        RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
    ),
}

results = {}

for name, model in models.items():
    print(f"\n{'=' * 50}")
    print("Model:", name)

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(
        y_test, predictions, zero_division=0
    )
    recall = recall_score(
        y_test, predictions, zero_division=0
    )
    f1 = f1_score(
        y_test, predictions, zero_division=0
    )

    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-score:  {f1:.4f}")

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["Not lying", "Lying"],
            zero_division=0,
        )
    )

    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions, labels=[0, 1]))

    results[name] = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

np.savez_compressed(
    OUTPUT / "depth_baseline_results.npz",
    y_test=y_test,
    test_sequences=groups[test_idx],
    **{
        name.replace(" ", "_").lower(): np.array(list(metrics.values()))
        for name, metrics in results.items()
    },
)

print("\nSaved metrics:", OUTPUT / "depth_baseline_results.npz")
