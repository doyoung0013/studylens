# utils.py

import requests
import cv2
import time
import base64
from io import BytesIO
from PIL import Image
from config import SERVER_BASE_URL, LOGIN_USERNAME, LOGIN_PASSWORD


# ----------------------------
# 1) JWT 로그인
# ----------------------------
def get_access_token():
    url = f"{SERVER_BASE_URL}/auth/login/"
    data = {"username": LOGIN_USERNAME, "password": LOGIN_PASSWORD}

    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()['access']
    else:
        print("❌ 로그인 실패:", response.text)
        return None


# ----------------------------
# 2) 공부 세션 시작
# ----------------------------
def study_start(access_token):
    url = f"{SERVER_BASE_URL}/study/start/"
    headers = {"Authorization": f"Bearer {access_token}"}

    res = requests.post(url, headers=headers)
    return res.json()


# ----------------------------
# 3) 공부 세션 종료
# ----------------------------
def study_end(access_token):
    url = f"{SERVER_BASE_URL}/study/end/"
    headers = {"Authorization": f"Bearer {access_token}"}

    res = requests.post(url, headers=headers)
    return res.json()


# ----------------------------
# 4) 이미지 업로드
# ----------------------------
def upload_image(access_token, frame, session_id=None):

    # frame → JPEG 변환
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    buffer = BytesIO()
    pil_img.save(buffer, format="JPEG")
    buffer.seek(0)

    files = {"image": ("study.jpg", buffer, "image/jpeg")}
    data = {}

    if session_id is not None:
        data["session_id"] = str(session_id)

    headers = {"Authorization": f"Bearer {access_token}"}

    url = f"{SERVER_BASE_URL}/image/upload/"
    res = requests.post(url, headers=headers, files=files, data=data)

    return res.json()
