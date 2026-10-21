
import json
import time
from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "data" / "resident_faces" / "residents.json"

# Conservative starting threshold; validate using your own camera/photos.
MATCH_THRESHOLD = 0.50
PROCESS_EVERY_N_FRAMES = 3


def load_residents():
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Resident database not found: {DATABASE_FILE}"
        )

    with open(DATABASE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    residents = []
    for resident_id, details in data.items():
        embedding = np.asarray(details["embedding"], dtype=np.float32)
        norm = np.linalg.norm(embedding)

        if norm > 0:
            residents.append({
                "id": resident_id,
                "name": details["name"],
                "embedding": embedding / norm,
            })

    if not residents:
        raise ValueError("No valid resident embeddings found.")

    return residents


def main():
    residents = load_residents()

    app = FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=-1, det_size=(640, 640))

    cap = cv2.VideoCapture(2)

    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Could not open camera index 1 or 0.")
        return

    print("Live face recognition running. Press Q to quit.")

    frame_count = 0
    cached_faces = []
    last_process_time = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Could not read camera frame.")
            break

        frame_count += 1

        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            cached_faces = app.get(frame)
            last_process_time = time.time()

        for face in cached_faces:
            x1, y1, x2, y2 = map(int, face.bbox)
            query = np.asarray(face.normed_embedding, dtype=np.float32)

            best_resident = None
            best_similarity = -1.0

            for resident in residents:
                similarity = float(np.dot(query, resident["embedding"]))

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_resident = resident

            if (
                best_resident is not None
                and best_similarity >= MATCH_THRESHOLD
            ):
                label = (
                    f"{best_resident['name']} "
                    f"({best_resident['id']})"
                )
                box_color = (0, 200, 0)
            else:
                label = "Unknown Resident"
                box_color = (0, 0, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.putText(
                frame,
                f"{label} | Similarity: {best_similarity:.2f}",
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                box_color,
                2,
            )

        cv2.putText(
            frame,
            f"Registered residents: {len(residents)}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )

        cv2.imshow("Resident Face Recognition", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
