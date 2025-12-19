#SERVER_BASE_URL = "http://127.0.0.1:8000/api"  # Django 서버 주소
SERVER_BASE_URL = "https://doyoung.pythonanywhere.com/api"

LOGIN_USERNAME = "testuser"
LOGIN_PASSWORD = "1234"

DETECTION_THRESHOLD = 0.45     # YOLO confidence threshold
MIN_STUDY_DETECTION_SEC = 0    # 몇 초 이상 감지되면 "공부 시작" 인정

CAPTURE_INTERVAL_SEC = 60      # 공부 중일 때 몇 초마다 이미지 서버로 보낼지
