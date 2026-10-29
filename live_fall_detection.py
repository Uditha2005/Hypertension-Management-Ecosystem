from collections import defaultdict, deque
from pathlib import Path
import sys
import time
import threading
import tempfile
import os
import json
import urllib.request
import urllib.error

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

import cv2
import numpy as np
import joblib
from ultralytics import YOLO

from insightface.app import FaceAnalysis

BASE_DIR = Path(__file__).resolve().parent
COMPONENT_DIR = BASE_DIR / "ai" / "component2-behavioral"
sys.path.insert(0, str(COMPONENT_DIR / "src"))

from train_rf_common_split import extract_features
app = FastAPI(title="Component 2 Behavioral AI")


NODE_API_URL = os.getenv(
    "NODE_API_URL",
    "http://127.0.0.1:5000/api/behavioral/fall-events"
)


def persist_fall_event(
    resident_id=None,
    resident_name=None,
    track_id=None,
    probability=None,
    source="live_camera",
    video_time_seconds=None,
):
    """Save a confirmed fall event through the Node.js backend."""

    payload = {
        "residentId": resident_id,
        "residentName": resident_name,
        "trackId": str(track_id) if track_id is not None else None,
        "probability": probability,
        "source": source,
        "videoTimeSeconds": video_time_seconds,
    }

    request = urllib.request.Request(
        NODE_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(
                f"[Fall History] Saved event: "
                f"{result.get('event', {}).get('id')}"
            )
            return True

    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"[Fall History] Could not save event: {error}")
        return False


from fastapi.middleware.cors import CORSMiddleware


# Allow the React development server to call the Python AI API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Populated by main() after the existing AI models are initialized.
ai_components = {}
video_analysis_lock = threading.Lock()

frame_lock = threading.Lock()
latest_frame = None

ai_status = {
    "connected": False,
    "camera": "CAM-01",
    "resident": None,
    "residentName": None,
    "residentId": None,
    "fallDetected": False,
    "lastEvent": None,
    "updatedAt": None,
}

def generate_frames():
    while True:
        with frame_lock:
            frame = latest_frame.copy() if latest_frame is not None else None

        if frame is None:
            time.sleep(0.1)
            continue

        success, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )

        if not success:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )
from fastapi.responses import Response

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_frame")
def video_frame():
    with frame_lock:
        if latest_frame is None:
            raise HTTPException(
                status_code=503,
                detail="Camera frame is not available yet.",
            )

        success, encoded_frame = cv2.imencode(".jpg", latest_frame.copy())

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Could not encode camera frame.",
        )

    return Response(
        content=encoded_frame.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "component2-behavioral"}

@app.get("/api/behavioral/status")
def get_behavioral_status():
    with frame_lock:
        return {
            **ai_status,
            "connected": latest_frame is not None,
        }


def _analyze_uploaded_video(video_path: str):
    """Run the existing pose, face-recognition, and Random Forest pipeline on a video file."""
    if not ai_components:
        raise HTTPException(
            status_code=503,
            detail="AI models are not initialized. Start live_fall_detection.py first.",
        )

    # A separate YOLO tracker prevents uploaded-video tracking state from
    # interfering with the live webcam tracker.
    residents = ai_components["residents"]
    face_app = ai_components["face_app"]
    device = ai_components["device"]
    model = ai_components["model"]
    feature_extractor = ai_components["feature_extractor"]
    video_pose_model = YOLO(POSE_MODEL)

    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=400,
            detail="Could not open the uploaded video."
        )

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if not video_fps or video_fps <= 0:
        video_fps = 30.0


    buffers = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    positive_counts = defaultdict(int)
    fall_start_frames = {}
    track_residents = {}
    last_face_seen = {}
    face_results = []
    frame_number = 0
    processed_frames = 0
    best_fall_probability = 0.0
    detected_events = []
    recognized_residents = {}

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_number += 1
            processed_frames += 1

            if frame_number % FACE_PROCESS_EVERY_N_FRAMES == 0:
                face_results = face_app.get(frame)

            height, width = frame.shape[:2]
            result = video_pose_model.track(
                frame,
                persist=True,
                classes=[0],
                tracker=str(COMPONENT_DIR / "config" / "botsort_custom.yaml"),
                verbose=False,
            )[0]

            if result.keypoints is None or result.keypoints.data is None:
                continue

            keypoints = result.keypoints.data.cpu().numpy()
            boxes = result.boxes
            track_ids = (
                boxes.id.int().cpu().tolist()
                if boxes is not None and boxes.id is not None
                else None
            )

            for i, points in enumerate(keypoints):
                if track_ids is None or i >= len(track_ids):
                    continue

                track_id = int(track_ids[i])
                person_name = "Unknown Resident"
                person_id = None

                if boxes is not None and i < len(boxes):
                    px1, py1, px2, py2 = (
                        boxes.xyxy[i].cpu().numpy().astype(int)
                    )

                    best_face = None
                    best_overlap = 0.0
                    for face in face_results:
                        fx1, fy1, fx2, fy2 = map(int, face.bbox)
                        face_cx = (fx1 + fx2) / 2
                        face_cy = (fy1 + fy2) / 2

                        if px1 <= face_cx <= px2 and py1 <= face_cy <= py2:
                            face_area = max((fx2 - fx1) * (fy2 - fy1), 1)
                            person_area = max((px2 - px1) * (py2 - py1), 1)
                            overlap = face_area / person_area
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_face = face

                    if best_face is not None:
                        query_embedding = np.asarray(
                            best_face.normed_embedding, dtype=np.float32
                        )
                        best_similarity = -1.0
                        matched_resident = None

                        for rid, resident in residents.items():
                            similarity = float(
                                np.dot(query_embedding, resident["embedding"])
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
                            track_residents[track_id] = (person_id, person_name)
                            last_face_seen[track_id] = time.time()

                if person_id is None:
                    previous = track_residents.get(track_id)
                    last_seen = last_face_seen.get(track_id, 0.0)
                    if previous is not None and time.time() - last_seen <= FACE_IDENTITY_TIMEOUT:
                        person_id, person_name = previous

                recognized_residents[track_id] = {
                    "residentId": person_id,
                    "residentName": person_name,
                }

                points = points.astype(np.float32).copy()
                points[:, 0] = points[:, 0] * 640.0 / max(width, 1)
                points[:, 1] = points[:, 1] * 480.0 / max(height, 1)
                points[:, 0] /= 640.0
                points[:, 1] /= 480.0

                invisible = points[:, 2] <= 0
                points[invisible, :2] = 0.0
                buffers[track_id].append(points)

                if len(buffers[track_id]) < WINDOW_SIZE:
                    continue

                sequence = np.stack(buffers[track_id]).astype(np.float32)
                # Random Forest training uses the same 244-feature extractor.
                # Keep the raw normalized skeleton coordinates; do not apply
                # the CNN/LSTM coordinate standardization here.
                feature_vector = np.asarray(
                    feature_extractor(np.expand_dims(sequence, axis=0)),
                    dtype=np.float32,
                ).reshape(1, -1)

                if feature_vector.shape[1] != model.n_features_in_:
                    raise ValueError(
                        "Random Forest feature mismatch: live extractor "
                        f"produced {feature_vector.shape[1]} features, but "
                        f"the model expects {model.n_features_in_}."
                    )

                class_probabilities = model.predict_proba(feature_vector)[0]
                class_indices = list(model.classes_)
                if 1 not in class_indices:
                    raise ValueError(
                        "Loaded Random Forest model has no fall class label 1."
                    )
                fall_probability = float(
                    class_probabilities[class_indices.index(1)]
                )
                best_fall_probability = max(best_fall_probability, fall_probability)

                
                if fall_probability >= FALL_THRESHOLD:
                    # Remember the first frame of the current positive sequence.
                    if positive_counts[track_id] == 0:
                        fall_start_frames[track_id] = frame_number

                    positive_counts[track_id] += 1

                    # Confirm only after the required consecutive positive windows.
                    if positive_counts[track_id] == FALL_CONFIRM_WINDOWS:
                        start_frame = fall_start_frames.get(
                            track_id, frame_number
                        )

                        detected_events.append({
                            "type": "fall",
                            "residentId": person_id,
                            "residentName": person_name,
                            "trackId": track_id,
                            "probability": fall_probability,

                            # Frame where the positive sequence began.
                            "startFrame": start_frame,

                            # Frame where the fall was confirmed.
                            "confirmedFrame": frame_number,

                            # Approximate positions on the uploaded video's timeline.
                            "startTimeSeconds": round(
                                start_frame / video_fps, 2
                            ),
                            "confirmedTimeSeconds": round(
                                frame_number / video_fps, 2
                            ),
                        })
                else:
                    positive_counts[track_id] = 0
                    fall_start_frames.pop(track_id, None)


    finally:
        cap.release()

    if processed_frames == 0:
        raise HTTPException(status_code=400, detail="The uploaded video contains no readable frames.")

    # Prefer the first confirmed fall event's identity; otherwise report the
    # first tracked person's most recently available identity.
    selected_event = detected_events[0] if detected_events else None
    selected_identity = None
    if selected_event:
        selected_identity = {
            "residentId": selected_event["residentId"],
            "residentName": selected_event["residentName"],
        }
    elif recognized_residents:
        selected_identity = next(iter(recognized_residents.values()))
        
    for event in detected_events:
        persist_fall_event(
            resident_id=event.get("residentId"),
            resident_name=event.get("residentName"),
            track_id=event.get("trackId"),
            probability=event.get("probability"),
            source="uploaded_video",
            video_time_seconds=event.get("confirmedTimeSeconds"),
        )


    
    return {
        "success": True,
        "source": "uploaded_video",
        "processedFrames": processed_frames,
        "videoFps": round(video_fps, 2),
        "fallDetected": bool(detected_events),
        "bestFallProbability": round(best_fall_probability, 4),
        "resident": selected_identity,
        "events": detected_events,
        "message": (
            "Fall detected in uploaded video."
            if detected_events
            else "No confirmed fall detected in uploaded video."
        ),
    }



@app.post("/api/behavioral/analyze-video")
def analyze_uploaded_video(file: UploadFile = File(...)):
    """Upload a recorded video and analyze it using the existing trained AI model."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Choose a video file first.")

    allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    extension = Path(file.filename).suffix.lower()
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported video format. Use MP4, AVI, MOV, MKV, or WEBM.",
        )

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temporary_file:
            temporary_path = temporary_file.name
            total_bytes = 0
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > 100 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Video must be 100 MB or smaller.")
                temporary_file.write(chunk)

        # Serialize video jobs so multiple uploads do not compete for model resources.
        with video_analysis_lock:
            return _analyze_uploaded_video(temporary_path)
    finally:
        file.file.close()
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


CHECKPOINT = COMPONENT_DIR / "models" / "rf_fall_detection_common_split.joblib"
POSE_MODEL = "yolo11n-pose.pt"
CAMERA_INDEX = 4
WINDOW_SIZE = 30

RESIDENT_DATABASE = (
    COMPONENT_DIR / "data" / "resident_faces" / "residents.json"
)

FACE_PROCESS_EVERY_N_FRAMES = 10
FACE_MATCH_THRESHOLD = 0.50
FACE_IDENTITY_TIMEOUT = 10.0

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

    global latest_frame, ai_status
    
    residents = load_residents(RESIDENT_DATABASE)

    face_app = FaceAnalysis(
        name="buffalo_l",
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    face_app.prepare(ctx_id=0, det_size=(640, 640))

    print("Registered residents:", list(residents.keys()))
    print("Face recognition initialized.")

    if not CHECKPOINT.exists():
        raise FileNotFoundError(
            f"Random Forest model not found: {CHECKPOINT}\n"
            "Run src/train_rf_common_split.py first."
        )

    model = joblib.load(CHECKPOINT)

    if not hasattr(model, "predict_proba"):
        raise TypeError(
            "Loaded Random Forest model does not support predict_proba."
        )

    if not hasattr(model, "n_features_in_"):
        raise TypeError(
            "Loaded model does not expose n_features_in_; "
            "make sure the trained Random Forest artifact is being loaded."
        )

    device = "CPU (Random Forest / scikit-learn)"
    print("Loaded Random Forest model:", CHECKPOINT)
    print("Expected feature count:", model.n_features_in_)

    import torch

    if torch.cuda.is_available():
        pose_model = YOLO(POSE_MODEL)
        pose_device = 0
        print("YOLO GPU:", torch.cuda.get_device_name(0))
    else:
        pose_model = YOLO(POSE_MODEL)
        pose_device = "cpu"
        print("YOLO running on CPU")

    ai_components.update({
        "residents": residents,
        "face_app": face_app,
        "device": device,
        "model": model,
        "feature_extractor": extract_features,
    })

    cap = cv2.VideoCapture(CAMERA_INDEX)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        cap.release()
        print("Webcam is unavailable. Recorded-video analysis API will remain active.")
        print("Use POST /api/behavioral/analyze-video to analyze an uploaded video.")
        print("Press Ctrl+C in this terminal to stop the service.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping Component 2 AI service.")
        return

    # One independent temporal window and alert state per tracked person.
    buffers = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    positive_counts = defaultdict(int)
    fall_recorded = defaultdict(bool)
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
                device=pose_device,
                verbose=False
            )[0]


            display = frame.copy()
            with frame_lock:
                latest_frame = display.copy()
            now = time.time()

            if result.keypoints is not None and result.keypoints.data is not None:
                keypoints = result.keypoints.data.cpu().numpy()
                track_ids = None

                if result.boxes is not None and result.boxes.id is not None:
                    track_ids = result.boxes.id.int().cpu().tolist()

                boxes = result.boxes
                #result.plot()

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
                        print("DEBUG sequence shape:", np.asarray(sequence).shape)
                        print("DEBUG sequence type:", type(sequence))
                        # Use exactly the same feature extraction function
                        # as Random Forest training. The sequence already has
                        # normalized image coordinates in [0, 1].
                        feature_vector = np.asarray(
                            extract_features(np.expand_dims(sequence, axis=0)),
                            dtype=np.float32
                        ).reshape(1, -1)

                        if feature_vector.shape[1] != model.n_features_in_:
                            raise ValueError(
                                "Random Forest feature mismatch: live extractor "
                                f"produced {feature_vector.shape[1]} features, "
                                f"but model expects {model.n_features_in_}."
                            )

                        class_probabilities = model.predict_proba(feature_vector)[0]
                        class_indices = list(model.classes_)
                        if 1 not in class_indices:
                            raise ValueError(
                                "Loaded Random Forest model has no fall class label 1."
                            )

                        fall_probability = float(
                            class_probabilities[class_indices.index(1)]
                        )
                        normal_probability = 1.0 - fall_probability

                        with frame_lock:
                            ai_status.update({
                                "resident": person_name,
                                "residentName": person_name,
                                "residentId": person_id,
                                "fallDetected": (
                                    fall_probability >= FALL_THRESHOLD
                                    and positive_counts[track_id] + 1 >= FALL_CONFIRM_WINDOWS
                                ),
                                "lastEvent": (
                                    {
                                        "type": "fall",
                                        "residentName": person_name,
                                        "residentId": person_id,
                                        "trackId": track_id,
                                        "probability": fall_probability,
                                        "timestamp": time.time(),
                                    }
                                    if (
                                        fall_probability >= FALL_THRESHOLD
                                        and positive_counts[track_id] + 1 >= FALL_CONFIRM_WINDOWS
                                    )
                                    else ai_status.get("lastEvent")
                                ),
                                "updatedAt": time.time(),
                            })

                        print(
                            f"Track {track_id} | "
                            f"Normal: {normal_probability:.3f} | "
                            f"Fall: {fall_probability:.3f}"
                        )

                        if fall_probability >= FALL_THRESHOLD:
                            positive_counts[track_id] += 1
                        else:
                            positive_counts[track_id] = 0
                            fall_recorded[track_id] = False

                        
                        if positive_counts[track_id] >= FALL_CONFIRM_WINDOWS:
                            label = (
                                f"FALL DETECTED - {identity_label} "
                                f"({fall_probability:.0%})"
                            )
                            color = (0, 0, 255)

                            if now - last_alert[track_id] >= ALERT_COOLDOWN_SECONDS:
                                print(
                                    f"[DEMO ALERT] FALL DETECTED | "
                                    f"Resident: {person_name} | "
                                    f"Resident ID: {person_id or 'Unknown'} | "
                                    f"Probability: {fall_probability:.3f}"
                                )
                                last_alert[track_id] = now

                                # Save the confirmed fall only once
                                if not fall_recorded[track_id]:
                                    saved = persist_fall_event(
                                        resident_id=person_id,
                                        resident_name=person_name,
                                        track_id=track_id,
                                        probability=fall_probability,
                                        source="live_camera",
                                    )

                                    if saved:
                                        fall_recorded[track_id] = True

                        elif fall_probability >= 0.75:
                            label = (
                                f"WARNING - MAY BE FALLING "
                                f"({fall_probability:.0%})"
                            )
                            color = (0, 165, 255)

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
    import threading
    import uvicorn

    api_thread = threading.Thread(
        target=lambda: uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
        ),
        daemon=True,
    )
    api_thread.start()

    main()

