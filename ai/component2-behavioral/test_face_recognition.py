
import cv2
from insightface.app import FaceAnalysis

# Initialize InsightFace
app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)
app.prepare(ctx_id=-1, det_size=(640, 640))

# Open DroidCam (current camera index: 1)
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("ERROR: Cannot open camera index 1")
    print("Try changing VideoCapture(1) to VideoCapture(0)")
    raise SystemExit(1)

print("Face detection started. Press Q to quit.")

while True:
    ret, frame = cap.read()

    if not ret:
        print("ERROR: Cannot read frame from camera")
        break

    faces = app.get(frame)

    for face in faces:
        x1, y1, x2, y2 = map(int, face.bbox)

        # Draw face bounding box
        cv2.rectangle(
            frame, (x1, y1), (x2, y2),
            (0, 255, 0), 2
        )

        # Display face detection score
        score = float(face.det_score)
        cv2.putText(
            frame,
            f"Face: {score:.2f}",
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

    cv2.putText(
        frame,
        f"Faces detected: {len(faces)}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )

    cv2.imshow("Resident Face Detection Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
