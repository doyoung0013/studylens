"""YOLOv5 추론 + 프레임 품질 검사."""
from dataclasses import dataclass

import cv2
import numpy as np

import config


@dataclass
class Detection:
    person: bool
    book: bool
    laptop: bool
    phone: bool

    @property
    def study_object(self):
        return self.book or self.laptop


# ------------------------------------------------------------------
# 프레임 품질
# ------------------------------------------------------------------
def to_gray(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def is_low_brightness(gray, threshold=config.LOW_BRIGHTNESS_THRESHOLD):
    return float(np.mean(gray)) < threshold


def is_camera_shaking(prev_gray, gray, threshold=config.MOTION_THRESHOLD):
    if prev_gray is None or prev_gray.shape != gray.shape:
        return False
    return float(np.mean(cv2.absdiff(prev_gray, gray))) > threshold


# ------------------------------------------------------------------
# 객체 감지
# ------------------------------------------------------------------
class Detector:
    def __init__(self, model_name=config.YOLO_MODEL):
        import torch  # 무거운 의존성은 실제 사용할 때만 로드

        self.model = torch.hub.load("ultralytics/yolov5", model_name)
        # 클래스별 임계값은 아래에서 따로 적용하므로 모델 임계값은 가장 낮은 값으로
        self.model.conf = min(
            config.PERSON_CONF_THRESHOLD,
            config.BOOK_CONF_THRESHOLD,
            config.LAPTOP_CONF_THRESHOLD,
            config.PHONE_CONF_THRESHOLD,
        )
        self.model.classes = [config.CLASS_PERSON, config.CLASS_LAPTOP, config.CLASS_CELL_PHONE, config.CLASS_BOOK]

    def detect(self, frame):
        """BGR 프레임 → (Detection, YOLO results)."""
        results = self.model(np.ascontiguousarray(frame[..., ::-1]))  # YOLOv5 hub 모델은 RGB 입력
        return parse_results(results.xyxy[0].tolist()), results


def parse_results(rows):
    """[[x1, y1, x2, y2, conf, cls], ...] → Detection (클래스별 임계값 적용)."""
    thresholds = {
        config.CLASS_PERSON: config.PERSON_CONF_THRESHOLD,
        config.CLASS_BOOK: config.BOOK_CONF_THRESHOLD,
        config.CLASS_LAPTOP: config.LAPTOP_CONF_THRESHOLD,
        config.CLASS_CELL_PHONE: config.PHONE_CONF_THRESHOLD,
    }
    found = set()
    for *_box, conf, cls in rows:
        cls = int(cls)
        if cls in thresholds and conf >= thresholds[cls]:
            found.add(cls)
    return Detection(
        person=config.CLASS_PERSON in found,
        book=config.CLASS_BOOK in found,
        laptop=config.CLASS_LAPTOP in found,
        phone=config.CLASS_CELL_PHONE in found,
    )


def encode_for_upload(frame, max_side=config.UPLOAD_MAX_SIDE, quality=config.UPLOAD_JPEG_QUALITY):
    """업로드용으로 리사이즈 + JPEG 인코딩한 bytes."""
    h, w = frame.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG 인코딩 실패")
    return buf.tobytes()
