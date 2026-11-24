"""
StudyLens Edge 설정.

계정 정보 같은 비밀값은 코드에 두지 않고 환경변수 또는 edge/.env 파일에서 읽는다.
(edge/.env.example 참고)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def _float(name, default):
    return float(os.environ.get(name, default))


def _bool(name, default):
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


# ------------------------------------------------------------------
# 서버 / 계정
# ------------------------------------------------------------------
SERVER_BASE_URL = os.environ.get("STUDYLENS_SERVER", "https://doyoung.pythonanywhere.com/api").rstrip("/")
LOGIN_USERNAME = os.environ.get("STUDYLENS_USERNAME", "")
LOGIN_PASSWORD = os.environ.get("STUDYLENS_PASSWORD", "")
REQUEST_TIMEOUT_SEC = _float("STUDYLENS_REQUEST_TIMEOUT", 10)

# ------------------------------------------------------------------
# 카메라 / 추론
# ------------------------------------------------------------------
CAMERA_INDEX = int(os.environ.get("STUDYLENS_CAMERA", 0))
YOLO_MODEL = os.environ.get("STUDYLENS_YOLO_MODEL", "yolov5s")
INFERENCE_FPS = _float("STUDYLENS_INFERENCE_FPS", 4)   # 초당 추론 횟수 (CPU 사용량 조절)
SHOW_PREVIEW = _bool("STUDYLENS_SHOW_PREVIEW", True)    # 감지 결과 창 표시 (headless 환경이면 0)

# COCO 클래스 번호
CLASS_PERSON = 0
CLASS_LAPTOP = 63
CLASS_CELL_PHONE = 67
CLASS_BOOK = 73

PERSON_CONF_THRESHOLD = 0.45
BOOK_CONF_THRESHOLD = 0.25
LAPTOP_CONF_THRESHOLD = 0.25
PHONE_CONF_THRESHOLD = 0.35

# ------------------------------------------------------------------
# 프레임 품질 필터
# ------------------------------------------------------------------
LOW_BRIGHTNESS_THRESHOLD = 40   # 평균 밝기(0~255) 미만이면 저조도로 판단
MOTION_THRESHOLD = 25           # 연속 프레임 평균 차이가 이보다 크면 흔들림으로 판단

# ------------------------------------------------------------------
# 공부 상태 판정 (study_state.py)
# ------------------------------------------------------------------
VOTE_WINDOW_SEC = 1.5           # 최근 N초 프레임 다수결로 감지 여부를 판단 (한두 프레임 튐 방지)
VOTE_RATIO = 0.5                # 윈도 안에서 이 비율 이상 감지되면 '있음'
MIN_STUDY_DETECTION_SEC = 3     # 사람+책(노트북)이 이 시간 이상 계속 보여야 공부 시작
PERSON_ABSENT_SEC = 120         # 사람이 이 시간 이상 안 보이면 공부 종료
STUDY_OBJECT_MEMORY_SEC = 180   # 책/노트북이 이 시간 이상 안 보이면 공부 종료

# 딴짓(휴대폰) 판정
PHONE_MIN_SEC = 5               # 휴대폰이 이 시간 이상 계속 보이면 딴짓 시작
PHONE_CLEAR_SEC = 5             # 휴대폰이 이 시간 이상 안 보이면 딴짓 종료

# ------------------------------------------------------------------
# 이미지 업로드
# ------------------------------------------------------------------
CAPTURE_INTERVAL_SEC = 60       # 공부 중 이미지 업로드 주기
UPLOAD_MAX_SIDE = 960           # 업로드 전 긴 변 리사이즈 (px)
UPLOAD_JPEG_QUALITY = 80

# ------------------------------------------------------------------
# 오프라인 큐 / 로그
# ------------------------------------------------------------------
QUEUE_DIR = Path(os.environ.get("STUDYLENS_QUEUE_DIR", BASE_DIR / "edge_queue"))
RETRY_BASE_SEC = 2              # 전송 실패 시 재시도 간격 (지수 백오프 시작값)
RETRY_MAX_SEC = 60
LOG_FILE = BASE_DIR / "edge.log"
LOG_THROTTLE_SEC = 30           # 같은 경고(저조도 등)는 이 간격에 한 번만 기록
