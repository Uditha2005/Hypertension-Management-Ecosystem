"""Run prescription OCR in the separate OCR Python environment."""

import json
import sys
import time
from pathlib import Path


def stage(message):
    print(
        f"[prescription OCR] {message}",
        file=sys.stderr,
        flush=True,
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: paddle_worker.py IMAGE_PATH OUTPUT_PATH"
        )

    started = time.monotonic()

    stage(
        "Worker started; importing Pillow and PaddleOCR dependencies..."
    )

    from PIL import Image
    from prescription_paddle import read_prescription

    stage("Imports complete; opening image...")

    image_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    with Image.open(image_path) as image:
        stage("Loading OCR models and running prediction...")
        payload = read_prescription(image)

    stage("Prediction complete; writing result...")

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    stage(f"Finished in {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()