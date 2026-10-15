
import csv
import re
from pathlib import Path

import numpy as np

base = Path("ai/component2-behavioral/data/external")
skeleton_dir = Path("ai/component2-behavioral/data/processed/skeletons")

# Map each sequence to its available skeleton frame numbers.
skeleton_frames = {}

for path in skeleton_dir.glob("*.npz"):
    match = re.match(r"((?:fall|adl)-\d+)-cam(\d+)", path.stem)
    if not match:
        continue

    sequence = match.group(1)
    camera = int(match.group(2))

    with np.load(path, allow_pickle=False) as data:
        frames = set()

        for name in data["frame_names"]:
            frame_match = re.search(r"rgb-(\d+)", str(name))
            if frame_match:
                frames.add(int(frame_match.group(1)))

    skeleton_frames[(sequence, camera)] = frames

total = 0
matched = 0
missing = []

files = [
    "urfall-cam0-falls.csv",
    "urfall-cam0-adls.csv",
]

for filename in files:
    with open(base / filename, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) < 3:
                continue

            sequence = row[0]
            frame = int(row[1])
            label = int(row[2])

            # Exclude temporary falling-transition frames.
            if label == 0:
                continue

            total += 1
            frames = skeleton_frames.get((sequence, 0), set())

            if frame in frames:
                matched += 1
            else:
                missing.append((sequence, frame))

print("Total eligible depth rows:", total)
print("Matching skeleton frames:", matched)
print("Missing skeleton frames:", len(missing))
print("First missing frames:", missing[:20])

if total:
    print("Alignment percentage:", round(matched / total * 100, 2), "%")
