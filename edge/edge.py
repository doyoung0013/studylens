import torch
import cv2
import time
from edge_utils import get_access_token, study_start, study_end, upload_image
from config import DETECTION_THRESHOLD, MIN_STUDY_DETECTION_SEC, CAPTURE_INTERVAL_SEC

# YOLO 모델 로드
print("📦 YOLOv5 모델 로딩 중...")
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
model.conf = DETECTION_THRESHOLD


def detect_person_and_book(results):
    """
    YOLO 결과에서 person & book 동시 감지 여부 판정
    """
    has_person = False
    has_book = False

    for *box, conf, cls in results.xyxy[0]:
        label = int(cls)

        if label == 0:  # person
            has_person = True
        if label == 73:  # book
            has_book = True

    return has_person and has_book


def main():
    access_token = get_access_token()
    if not access_token:
        return

    cap = cv2.VideoCapture(0)

    studying = False
    session_id = None
    detected_start_time = None
    last_capture_time = 0

    print("📷 웹캠 시작!")

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # YOLO 모델 추론
        results = model(frame)

        detected = detect_person_and_book(results)

        now = time.time()

        # ---------------------------
        # 공부 시작 판별
        # ---------------------------
        if detected:
            if detected_start_time is None:
                detected_start_time = now

            # 일정 시간 이상 지속되면 공부 시작으로 인정
            if not studying and (now - detected_start_time >= MIN_STUDY_DETECTION_SEC):
                print("📚 공부 상태 감지 → 서버에 Start 요청")
                res = study_start(access_token)
                studying = True
                session_id = res["session"]["id"]
                last_capture_time = now  # 시작하자마자 캡처는 하지 않음

        # ---------------------------
        # 공부 종료 판별
        # ---------------------------
        else:
            detected_start_time = None

            if studying:
                print("🛑 공부 종료 감지 → 서버 End 요청")
                study_end(access_token)
                studying = False
                session_id = None

        # ---------------------------
        # 공부 중이면 일정 간격으로 사진 업로드
        # ---------------------------
        if studying and (now - last_capture_time >= CAPTURE_INTERVAL_SEC):
            print("📤 이미지 업로드 중...")
            upload_image(access_token, frame, session_id)
            last_capture_time = now

        # 화면 출력
        cv2.imshow("StudyLens Edge", results.render()[0])

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 종료 시 세션 정리
    if studying:
        study_end(access_token)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
