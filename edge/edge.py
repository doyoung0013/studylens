import torch
import cv2
import time
import numpy as np
from edge_utils import get_access_token, study_start, study_end, upload_image
from config import DETECTION_THRESHOLD, MIN_STUDY_DETECTION_SEC, CAPTURE_INTERVAL_SEC


LOG_FILE = "edge.log"

def write_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


LOW_BRIGHTNESS_THRESHOLD = 40
MOTION_THRESHOLD = 25


def is_low_brightness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray) < LOW_BRIGHTNESS_THRESHOLD


def is_camera_shaking(prev_frame, curr_frame):
    if prev_frame is None:
        return False
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(prev_gray, curr_gray)
    return np.mean(diff) > MOTION_THRESHOLD


# ------------------------------------
# YOLOv5 모델 로드 (로컬 Edge에서만 수행)
# ------------------------------------
print("📦 YOLOv5 모델 로딩 중...")
model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
model.conf = DETECTION_THRESHOLD


def detect_person_and_book(results):
    """
    YOLO 추론 결과에서
    - person
    - book
    이 동시에 존재하는지만 판별

    ⚠️ 개별 객체 추적 ❌
    ✅ 클래스 단위 존재 여부만 판단 (요청 최소화 목적)
    """
    has_person = False
    has_book = False

    for *box, conf, cls in results.xyxy[0]:
        label = int(cls)

        if label == 0:   # person
            has_person = True
        if label == 73:  # book
            has_book = True

    return has_person and has_book


def main():
    # ------------------------------------
    # 서버 인증 (JWT)
    # Edge는 서버에 먼저 접속하는 클라이언트 역할
    # ------------------------------------
    access_token = get_access_token()
    if not access_token:
        write_log("❌ 서버 인증 실패")
        return

    cap = cv2.VideoCapture(0)

    # ------------------------------------
    # 상태 관리 변수
    # ------------------------------------
    studying = False       
    session_id = None
    detected_start_time = None 
    lost_start_time = None  
    last_capture_time = 0    
    prev_frame = None      
    write_log("📷 Edge 시작")
    print("📷 웹캠 시작!")

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # ====================================================
        # 저조도 / 흔들림 환경 감지 → 자동 무시
        # ====================================================
        if is_low_brightness(frame):
            write_log("⚠️ 저조도 환경 → 프레임 무시")
            prev_frame = frame
            continue

        if is_camera_shaking(prev_frame, frame):
            write_log("⚠️ 카메라 흔들림 → 프레임 무시")
            prev_frame = frame
            continue

        prev_frame = frame

        # YOLO 추론 (프레임 단위 연산, 서버 요청 없음)
        results = model(frame)
        detected = detect_person_and_book(results)

        now = time.time()

        # ------------------------------------
        # 1️⃣ 공부 시작 판별 로직
        # ------------------------------------
        if detected:
            # 처음 감지된 시점 기록
            if detected_start_time is None:
                detected_start_time = now

            # 일정 시간 이상 지속될 경우에만 START 요청
            if (not studying and
                now - detected_start_time >= MIN_STUDY_DETECTION_SEC):

                print("📚 공부 상태 감지 → 서버에 Start 요청")

                res = study_start(access_token)
                studying = True
                session_id = res["session"]["id"]

                write_log("📚 공부 시작")

                # 종료 후보 시간 초기화
                lost_start_time = None

                # 시작 직후 즉시 캡처 방지
                last_capture_time = now

        # ------------------------------------
        # 2️⃣ 공부 종료 판별 로직 (안정성 강화)
        # ------------------------------------
        else:
            detected_start_time = None

            if studying:
                # 감지가 끊긴 최초 시점 기록
                if lost_start_time is None:
                    lost_start_time = now

                # 일정 시간 이상 감지 실패 시에만 END 요청
                # → 일시적인 인식 실패로 인한 종료 방지
                if now - lost_start_time >= MIN_STUDY_DETECTION_SEC:
                    print("🛑 공부 종료 감지 → 서버 End 요청")

                    study_end(access_token) 
                    studying = False
                    session_id = None
                    lost_start_time = None

                    write_log("🛑 공부 종료")

        # ------------------------------------
        # 3️⃣ 공부 중일 때만 이미지 업로드
        # ------------------------------------
        if studying and (now - last_capture_time >= CAPTURE_INTERVAL_SEC):
            print("📤 이미지 업로드 중...")

            # 이미지 업로드 주기 제한 → 서버 부하 및 네트워크 사용량 제어
            upload_image(access_token, frame, session_id)
            last_capture_time = now

            write_log("📤 이미지 업로드")

        cv2.imshow("StudyLens Edge", results.render()[0])

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if studying:
        study_end(access_token)
        write_log("🛑 강제 종료로 인한 공부 종료")

    cap.release()
    cv2.destroyAllWindows()
    write_log("🧹 Edge 종료")


if __name__ == "__main__":
    main()
