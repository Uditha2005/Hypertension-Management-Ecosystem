
from pathlib import Path
import csv
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = (
    ROOT / "ai" / "component2-behavioral"
    / "data" / "processed" / "results"
)

MODELS = [
    ("ST-GNN", "stgnn_common_split_results.npz"),
    ("LSTM", "lstm_common_split_results.npz"),
    ("1D CNN", "cnn_common_split_results.npz"),
    ("Random Forest", "rf_common_split_results.npz"),
]

def get_scalar(data, keys):
    for key in keys:
        if key in data.files:
            return float(np.asarray(data[key]).item())
    return None

def fmt(value, digits=4):
    return "N/A" if value is None else f"{value:.{digits}f}"

def main():
    rows = []

    for model_name, filename in MODELS:
        path = RESULTS_DIR / filename

        if not path.exists():
            print(f"Missing file: {path}")
            continue

        with np.load(path, allow_pickle=True) as data:
            accuracy = get_scalar(data, ["accuracy"])
            precision = get_scalar(data, ["fall_precision", "precision"])
            recall = get_scalar(data, ["fall_recall", "recall"])
            f1 = get_scalar(data, ["fall_f1", "f1"])
            train_time = get_scalar(
                data, ["training_seconds", "training_time"]
            )
            inference_time = get_scalar(
                data, ["inference_seconds", "inference_time"]
            )

            cm = np.asarray(data["confusion_matrix"])
            tn, fp, fn, tp = cm.ravel()

            rows.append({
                "Model": model_name,
                "Accuracy": accuracy,
                "Fall Precision": precision,
                "Fall Recall": recall,
                "Fall F1-score": f1,
                "True Negatives": int(tn),
                "False Positives": int(fp),
                "False Negatives": int(fn),
                "True Positives": int(tp),
                "Training Time (s)": train_time,
                "Inference Time (s)": inference_time,
            })

    if not rows:
        print("No model result files were found.")
        return

    # Display the comparison in PowerShell.
    headers = [
        "Model", "Accuracy", "Fall Precision", "Fall Recall",
        "Fall F1-score", "FP", "FN", "Train (s)", "Inference (s)"
    ]

    print("\n" + "=" * 100)
    print("FALL DETECTION MODEL COMPARISON")
    print("=" * 100)
    print("All models evaluated on the saved common test split (194 windows).")
    print("-" * 100)

    print(
        f"{headers[0]:<16} {headers[1]:>9} {headers[2]:>15} "
        f"{headers[3]:>12} {headers[4]:>13} {headers[5]:>5} "
        f"{headers[6]:>5} {headers[7]:>11} {headers[8]:>14}"
    )

    for row in rows:
        print(
            f"{row['Model']:<16} "
            f"{fmt(row['Accuracy']):>9} "
            f"{fmt(row['Fall Precision']):>15} "
            f"{fmt(row['Fall Recall']):>12} "
            f"{fmt(row['Fall F1-score']):>13} "
            f"{row['False Positives']:>5} "
            f"{row['False Negatives']:>5} "
            f"{fmt(row['Training Time (s)'], 2):>11} "
            f"{fmt(row['Inference Time (s)'], 4):>14}"
        )

    # Save a detailed CSV report.
    csv_path = RESULTS_DIR / "model_comparison_report.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # Save a readable Markdown report.
    md_path = RESULTS_DIR / "model_comparison_report.md"
    with open(md_path, "w", encoding="utf-8") as file:
        file.write("# Fall Detection Model Comparison\n\n")
        file.write(
            "Evaluation uses the saved common test split "
            "(194 windows: 168 normal, 26 fall).\n\n"
        )
        file.write(
            "| Model | Accuracy | Fall Precision | Fall Recall | "
            "Fall F1 | FP | FN | Training (s) | Inference (s) |\n"
        )
        file.write(
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        )

        for row in rows:
            values = [
                row["Model"],
                fmt(row["Accuracy"]),
                fmt(row["Fall Precision"]),
                fmt(row["Fall Recall"]),
                fmt(row["Fall F1-score"]),
                str(row["False Positives"]),
                str(row["False Negatives"]),
                fmt(row["Training Time (s)"], 2),
                fmt(row["Inference Time (s)"], 4),
            ]
            file.write("| " + " | ".join(values) + " |\n")

        file.write(
            "\n**Note:** N/A means that the timing value was not saved. "
            "Timing values are not necessarily directly comparable if "
            "they were measured differently.\n"
        )

    print("\nReports saved:")
    print(csv_path)
    print(md_path)

if __name__ == "__main__":
    main()
