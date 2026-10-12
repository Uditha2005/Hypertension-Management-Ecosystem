
import cv2
from ultralytics import YOLO

# YOLO pose model: detects people and estimates body keypoints
VIDEO_SOURCE = 0
POSE_MODEL = "yolo11n-pose.pt"


def main():
    model = YOLO(POSE_MODEL)
    cap = cv2.VideoCapture(VIDEO_SOURCE)

    if not cap.isOpened():
        print("ERROR: Could not open camera/video.")
        return

    print("Pose estimation started. Press Q to exit.")

    try:
        while True:
            success, frame = cap.read()

            if not success:
                print("Could not read frame.")
                break

            results = model.track(
                frame,
                persist=True,
                classes=[0],
                verbose=False
            )

            result = results[0]

            # Draw person boxes, skeleton and keypoints
            display_frame = result.plot()

            # Print keypoint data for detected people
            if result.keypoints is not None:
                keypoints = result.keypoints.data.cpu().numpy()

                for person_index, person_keypoints in enumerate(keypoints):
                    print(
                        f"Person {person_index + 1}: "
                        f"{person_keypoints.shape[0]} keypoints"
                    )

            cv2.imshow(
                "Elderly Monitoring - Pose Estimation",
                display_frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
