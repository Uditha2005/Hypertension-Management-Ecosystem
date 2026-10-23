from collections import defaultdict, deque
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from insightface.app import FaceAnalysis

BASE_DIR = Path(__file__).resolve().parent
COMPONENT_DIR = BASE_DIR / "ai" / "component2-behavioral"
sys.path.insert(0, str(COMPONENT_DIR / "src"))

from train_cnn_common_split import CNNFallDetector

CHECKPOINT = COMPONENT_DIR / "models" / "cnn_fall_detection_common_split.pt"
POSE_MODEL = "yolo11n-pose.pt"
CAMERA_INDEX = 2
WINDOW_SIZE = 30

RESIDENT_DATABASE = (
    COMPONENT_DIR / "data" / "resident_faces" / "residents.json"
)

FACE_PROCESS_EVERY_N_FRAMES = 5
FACE_MATCH_THRESHOLD = 0.50
FACE_IDENTITY_TIMEOUT = 3.0

# Consecutive positive windows required before raising a demo alert.
FALL_CONFIRM_WINDOWS = 3
FALL_THRESHOLD = 0.70
ALERT_COOLDOWN_SECONDS = 15


def load_residents(database_path):
    import json

    if not database_path.exists():
        raise FileNotFoundError(
            f"Resident database not found: {database_path}"
        )

    with open(database_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    residents = {}

    for resident_id, details in data.items():
        embedding = np.asarray(
            details["embedding"], dtype=np.float32
        )
        norm = np.linalg.norm(embedding)

        if norm > 0:
            residents[resident_id] = {
                "name": details["name"],
                "embedding": embedding / norm,
            }

    if not residents:
        raise ValueError("No valid resident embeddings found.")

    return residents

def main():
    
    residents = load_residents(RESIDENT_DATABASE)

    face_app = FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],
    )
    face_app.prepare(ctx_id=-1, det_size=(640, 640))

    print("Registered residents:", list(residents.keys()))
    print("Face recognition initialized.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(
        CHECKPOINT, map_location=device, weights_only=False
    )

    model = CNNFallDetector().to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    pose_model = YOLO(POSE_MODEL)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(
            "Could not open webcam. Close other camera apps and try again."
        )

    # One independent temporal window and alert state per tracked person.
    buffers = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    positive_counts = defaultdict(int)
    last_alert = defaultdict(float)

    
    face_results = []
    frame_number = 0

    # Maps YOLO tracking IDs to recently recognized residents.
    track_residents = {}
    last_face_seen = {}


    print("Live fall-detection demo started.")
    print("Device:", device)
    print("Press Q to quit.")
    print("This demo displays alerts locally; it does not send notifications.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Could not read webcam frame.")
                break


            
            frame_number += 1

            if frame_number % FACE_PROCESS_EVERY_N_FRAMES == 0:
                face_results = face_app.get(frame)

            
            height, width = frame.shape[:2]
            result = pose_model.track(
                frame,
                persist=True,
                classes=[0],
                tracker=str(
                    COMPONENT_DIR / "config" / "botsort_custom.yaml"
                ),
                verbose=False
            )[0]


            display = frame.copy()
            now = time.time()

            if result.keypoints is not None and result.keypoints.data is not None:
                keypoints = result.keypoints.data.cpu().numpy()
                track_ids = None

                if result.boxes is not None and result.boxes.id is not None:
                    track_ids = result.boxes.id.int().cpu().tolist()

                boxes = result.boxes
                result.plot()

                for i, points in enumerate(keypoints):
                    if track_ids is None or i >= len(track_ids):
                        continue

                    track_id = int(track_ids[i])

                    
                    # Associate detected faces with this tracked person.
                    person_name = "Unknown Resident"
                    person_id = None

                    if boxes is not None and i < len(boxes):
                        person_box = (
                            boxes.xyxy[i].cpu().numpy().astype(int)
                        )
                        px1, py1, px2, py2 = person_box

                        best_face = None
                        best_overlap = 0.0

                        for face in face_results:
                            fx1, fy1, fx2, fy2 = map(
                                int, face.bbox
                            )

                            face_cx = (fx1 + fx2) / 2
                            face_cy = (fy1 + fy2) / 2

                            # Face center must lie inside the person box.
                            if (
                                px1 <= face_cx <= px2
                                and py1 <= face_cy <= py2
                            ):
                                face_area = max(
                                    (fx2 - fx1) * (fy2 - fy1), 1
                                )
                                overlap = face_area / max(
                                    (px2 - px1) * (py2 - py1), 1
                                )

                                if overlap > best_overlap:
                                    best_overlap = overlap
                                    best_face = face

                        if best_face is not None:
                            query_embedding = np.asarray(
                                best_face.normed_embedding,
                                dtype=np.float32,
                            )

                            best_similarity = -1.0
                            matched_resident = None

                            for rid, resident in residents.items():
                                similarity = float(
                                    np.dot(
                                        query_embedding,
                                        resident["embedding"],
                                    )
                                )

                                if similarity > best_similarity:
                                    best_similarity = similarity
                                    matched_resident = (rid, resident)

                            if (
                                matched_resident is not None
                                and best_similarity >= FACE_MATCH_THRESHOLD
                            ):
                                person_id = matched_resident[0]
                                person_name = matched_resident[1]["name"]

                                track_residents[track_id] = (
                                    person_id, person_name
                                )
                                last_face_seen[track_id] = time.time()

                    # Reuse a recent identity briefly when the face
                    # is temporarily not visible.
                    if person_id is None:
                        previous = track_residents.get(track_id)
                        last_seen = last_face_seen.get(track_id, 0.0)

                        if (
                            previous is not None
                            and time.time() - last_seen
                            <= FACE_IDENTITY_TIMEOUT
                        ):
                            person_id, person_name = previous


                    # Training frames were 640x480 and normalized by those
                    # dimensions. Scale live coordinates to the same format.
                    print("Live keypoints shape:", points.shape)
                    points = points.astype(np.float32).copy()
                    points[:, 0] = points[:, 0] * 640.0 / max(width, 1)
                    points[:, 1] = points[:, 1] * 480.0 / max(height, 1)

                    points[:, 0] /= 640.0
                    points[:, 1] /= 480.0

                    invisible = points[:, 2] <= 0
                    points[invisible, :2] = 0.0

                    visible_joints = int(np.sum(points[:, 2] > 0))
                    mean_confidence = float(np.mean(points[:, 2]))

                    print(
                        f"Track {track_id} | "
                        f"Visible joints: {visible_joints}/17 | "
                        f"Mean keypoint confidence: {mean_confidence:.3f}"
                    )

                    buffers[track_id].append(points)

                    x1 = y1 = x2 = y2 = 0
                    if boxes is not None and i < len(boxes):
                        coords = boxes.xyxy[i].cpu().numpy().astype(int)
                        x1, y1, x2, y2 = coords.tolist()

                    identity_label = (
                        f"{person_name} [{person_id}]"
                        if person_id is not None
                        else f"Unknown Resident | Track {track_id}"
                    )

                    label = f"{identity_label}: collecting frames"

                    label = f"Person {track_id}: collecting frames"
                    color = (255, 200, 0)

                    if len(buffers[track_id]) == WINDOW_SIZE:
                        sequence = np.stack(buffers[track_id]).astype(
                            np.float32
                        )

                        # Match training normalization: use the saved
                        # training means/stds for visible x/y joints.
                        means = np.asarray(
                            checkpoint["coordinate_means"], dtype=np.float32
                        )
                        stds = np.asarray(
                            checkpoint["coordinate_stds"], dtype=np.float32
                        )

                        visible = sequence[:, :, 2] > 0
                        for feature in (0, 1):
                            values = sequence[:, :, feature]
                            values[visible] = (
                                values[visible] - means[feature]
                            ) / (stds[feature] + 1e-6)
                            values[~visible] = 0.0

                        tensor = torch.from_numpy(sequence).unsqueeze(0).to(device)

                        with torch.inference_mode():
                            probabilities = torch.softmax(
                                model(tensor), dim=1
                            )[0]

                        fall_probability = float(probabilities[1].item())

                        print(
                            f"Track {track_id} | "
                            f"Normal: {probabilities[0].item():.3f} | "
                            f"Fall: {fall_probability:.3f}"
                        )

                        if fall_probability >= FALL_THRESHOLD:
                            positive_counts[track_id] += 1
                        else:
                            positive_counts[track_id] = 0

                        if positive_counts[track_id] >= FALL_CONFIRM_WINDOWS:
                            label = (
                                f"FALL ALERT - {identity_label} "
                                f"({fall_probability:.0%})"
                            )
                            color = (0, 0, 255)

                            if now - last_alert[track_id] >= ALERT_COOLDOWN_SECONDS:
                                print(
                                    f"[DEMO ALERT] Fall prediction | "
                                    f"Resident: {person_name} | "
                                    f"Resident ID: {person_id or 'Unknown'} | "
                                    f"Track ID: {track_id} | "
                                    f"Probability: {fall_probability:.3f}"
                                )
                                last_alert[track_id] = now
                        else:
                            label = (
                                f"{identity_label}: "
                                f"Fall score {fall_probability:.0%}"
                            )
                            color = (0, 220, 0)

                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        display, label, (x1, max(y1 - 10, 25)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2
                    )

            cv2.imshow("Elderly Fall Detection - DEMO", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
