import json
import sys
from pathlib import Path

from PIL import Image
from prescription_paddle import read_prescription


def main():
    image_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    with Image.open(image_path) as image:
        payload = read_prescription(image)

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()