
import json
from pathlib import Path

import cv2
from insightface.app import FaceAnalysis

# Project paths
BASE_DIR = Path(__file__).resolve().parent
FACES_DIR = BASE_DIR / "data" / "resident_faces"
DATABASE_FILE = FACES_DIR / "residents.json"

FACES_DIR.mkdir(parents=True, exist_ok=True)

# Initialize face recognition model
app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)
app.prepare(ctx_id=-1, det_size=(640, 640))


def load_database():
    if DATABASE_FILE.exists():
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    resident_id = input("Resident ID: ").strip()
    resident_name = input("Resident name: ").strip()

    if not resident_id or not resident_name:
        print("ERROR: Resident ID and name are required.")
        return

    # Keep IDs safe for use as folder names
    if any(c in resident_id for c in r'\/:*?"<>|'):
        print("ERROR: Use a simple ID, e.g. R001.")
        return

    database = load_database()

    if resident_id in database:
        print("ERROR: This Resident ID is already registered.")
        print("Use a different ID or implement an explicit update process.")
        return

    print("\nUse a consented resident photo for registration.")
    photo_path = input("Full path to resident photo: ").strip().strip('"')

    image = cv2.imread(photo_path)

    if image is None:
        print("ERROR: Could not read that image.")
        return

    faces = app.get(image)

    if len(faces) == 0:
        print("ERROR: No face detected. Try a clearer, front-facing photo.")
        return

    if len(faces) > 1:
        print("ERROR: Multiple faces detected. Use a photo with one person.")
        return

    face = faces[0]
    embedding = face.normed_embedding

    # Save the embedding, not the original photo
    database[resident_id] = {
        "name": resident_name,
        "embedding": embedding.tolist()
    }

    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(database, f, indent=2)

    print(f"\nSUCCESS: Registered {resident_name} ({resident_id})")
    print(f"Database: {DATABASE_FILE}")
    print("Stored a face embedding; the original photo was not copied.")


if __name__ == "__main__":
    main()
