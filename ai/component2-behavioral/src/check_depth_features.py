
import csv
from pathlib import Path

base = Path("ai/component2-behavioral/data/external")

files = [
    "urfall-cam0-falls.csv",
    "urfall-cam0-adls.csv",
]

columns = [
    "sequence",
    "frame",
    "label",
    "HeightWidthRatio",
    "MajorMinorRatio",
    "BoundingBoxOccupancy",
    "MaxStdXZ",
    "HHmaxRatio",
    "H",
    "D",
    "P40",
]

print("Expected columns:", columns)

for filename in files:
    path = base / filename

    print(f"\n{'=' * 50}")
    print("File:", filename)

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    print("Total rows:", len(rows))
    print("Column counts:", sorted(set(len(row) for row in rows)))

    if rows:
        print("First row:", rows[0])

    invalid_rows = [
        (i + 1, len(row))
        for i, row in enumerate(rows)
        if len(row) != 11
    ]

    print("Rows with unexpected column count:", len(invalid_rows))

    labels = {}
    invalid_numeric = 0

    for row in rows:
        if len(row) != 11:
            continue

        labels[row[2]] = labels.get(row[2], 0) + 1

        try:
            int(row[1])
            int(row[2])

            for value in row[3:11]:
                float(value)
        except ValueError:
            invalid_numeric += 1

    print("Label counts:", labels)
    print("Rows with invalid numeric values:", invalid_numeric)
