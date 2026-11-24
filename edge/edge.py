"""
StudyLens Edge — 웹캠으로 공부 상태를 감지해서 서버에 기록한다.

실행:  python edge.py        (종료: 미리보기 창에서 q 또는 Ctrl+C)

구성
- detector.py     : YOLOv5 추론, 저조도/흔들림 검사, 업로드용 인코딩
- study_state.py  : 공부 시작/종료/딴짓/캡처 판정 상태머신 (순수 로직)
- api_client.py   : JWT 인증, 디스크 큐 + 백그라운드 전송, 재시도
"""
import logging
import sys
import time
import warnings
from logging.handlers import RotatingFileHandler

import cv2

import config
from api_client import AuthError, StudyLensClient
from detector import Detector, encode_for_upload, is_camera_shaking, is_low_brightness, to_gray
from study_state import StateConfig, StudyStateMachine

warnings.filterwarnings("ignore", category=FutureWarning)

log = logging.getLogger("studylens")

EVENT_MESSAGES = {
    "start": "📚 공부 시작",
    "end": "🛑 공부 종료",
    "distraction_start": "📱 딴짓(휴대폰) 감지 시작",
    "distraction_end": "✅ 딴짓 종료",
    "capture": "📤 이미지 업로드 예약",
}


def setup_logging():
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    file_handler = RotatingFileHandler(config.LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(console)


class ThrottledLogger:
    """같은 경고를 LOG_THROTTLE_SEC 마다 한 번만 기록 (매 프레임 로그 폭주 방지)."""

    def __init__(self, interval):
        self.interval = interval
        self._last = {}
        self._suppressed = {}

    def warning(self, key, message):
        now = time.time()
        if now - self._last.get(key, 0) >= self.interval:
            extra = self._suppressed.pop(key, 0)
            log.warning("%s%s", message, f" (이전 {extra}회 생략)" if extra else "")
            self._last[key] = now
        else:
            self._suppressed[key] = self._suppressed.get(key, 0) + 1


def draw_status(image, state):
    if state.distracted:
        text, color = "DISTRACTED (phone)", (0, 165, 255)
    elif state.studying:
        text, color = "STUDYING", (0, 200, 0)
    else:
        text, color = "IDLE", (180, 180, 180)
    cv2.putText(image, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    return image


def main():
    setup_logging()

    if not config.LOGIN_USERNAME or not config.LOGIN_PASSWORD:
        log.error("STUDYLENS_USERNAME / STUDYLENS_PASSWORD 가 설정되지 않았습니다. (edge/.env.example 참고)")
        return 1

    client = StudyLensClient(
        config.SERVER_BASE_URL, config.LOGIN_USERNAME, config.LOGIN_PASSWORD, config.QUEUE_DIR,
        timeout=config.REQUEST_TIMEOUT_SEC, retry_base=config.RETRY_BASE_SEC, retry_max=config.RETRY_MAX_SEC,
    )
    try:
        if client.login():
            log.info("✅ 서버 인증 성공")
        else:
            log.warning("⚠️ 서버에 연결할 수 없어 오프라인 모드로 시작합니다 (연결되면 자동 전송)")
    except AuthError as e:
        log.error("❌ 서버 인증 실패: %s", e)
        return 1

    pending = client.pending_count()
    if pending:
        log.info("이전 실행에서 못 보낸 이벤트 %d건을 전송합니다", pending)
    client.start_worker()

    log.info("📦 YOLOv5 모델 로딩 중...")
    detector = Detector()

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        log.error("❌ 카메라(%s)를 열 수 없습니다", config.CAMERA_INDEX)
        client.stop_worker()
        return 1

    state = StudyStateMachine(StateConfig.from_module(config))
    throttle = ThrottledLogger(config.LOG_THROTTLE_SEC)
    infer_interval = 1.0 / config.INFERENCE_FPS
    last_infer = 0.0
    prev_gray = None
    preview = None

    log.info("📷 Edge 시작 (추론 %.1f fps)", config.INFERENCE_FPS)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                throttle.warning("no_frame", "카메라 프레임을 읽지 못했습니다")
                time.sleep(0.1)
                continue

            gray = to_gray(frame)
            now = time.time()

            if now - last_infer >= infer_interval:
                last_infer = now

                # 저조도 / 흔들림 프레임은 판정에서 제외
                if is_low_brightness(gray):
                    throttle.warning("dark", "⚠️ 저조도 환경 → 프레임 무시")
                elif is_camera_shaking(prev_gray, gray):
                    throttle.warning("shake", "⚠️ 카메라 흔들림 → 프레임 무시")
                else:
                    detection, results = detector.detect(frame)
                    events = state.observe(now, detection.person, detection.study_object, detection.phone)
                    for event in events:
                        image = encode_for_upload(frame) if event.kind == "capture" else None
                        client.enqueue(event.kind, event.time, image)
                        log.info(EVENT_MESSAGES[event.kind])
                    if config.SHOW_PREVIEW:
                        preview = draw_status(results.render()[0][..., ::-1].copy(), state)

            prev_gray = gray

            if config.SHOW_PREVIEW:
                cv2.imshow("StudyLens Edge", preview if preview is not None else frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        log.info("Ctrl+C 입력")
    finally:
        for event in state.shutdown(time.time()):
            client.enqueue(event.kind, event.time)
            log.info("%s (프로그램 종료)", EVENT_MESSAGES[event.kind])
        cap.release()
        if config.SHOW_PREVIEW:
            cv2.destroyAllWindows()
        left = client.stop_worker(flush_timeout=10)
        if left:
            log.warning("전송하지 못한 이벤트 %d건은 다음 실행 때 전송됩니다", left)
        log.info("🧹 Edge 종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
