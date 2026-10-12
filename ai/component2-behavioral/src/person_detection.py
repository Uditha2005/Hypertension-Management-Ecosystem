
import cv2
from ultralytics import YOLO

# Use webcam 0 for the first test.
# Later, replace this with a CCTV RTSP URL or video file path.
VIDEO_SOURCE = 0

def main():
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(VIDEO_SOURCE)

    if not cap.isOpened():
        print("ERROR: Could not open camera/video.")
        return

    print("Person detection started. Press Q to exit.")

    while True:
        success, frame = cap.read()

        if not success:
            print("Could not read the next frame.")
            break

        results = model.track(
            frame,
            persist=True,
            classes=[0],
            verbose=False
        )

        display_frame = results[0].plot()

        cv2.imshow("Elderly Monitoring - Person Detection", display_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
