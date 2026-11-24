"""
StudyLens 서버 통신 클라이언트.

- JWT 로그인 + 만료 시 자동 갱신(refresh → 실패하면 재로그인)
- 모든 이벤트는 먼저 디스크 큐(QUEUE_DIR)에 저장한 뒤 백그라운드 스레드가 순서대로 전송
  → 네트워크가 끊겨도 카메라 루프가 멈추지 않고, 프로그램을 껐다 켜도 이벤트가 유실되지 않음
- 실패 시 지수 백오프 재시도. 서버가 400으로 거절한 이벤트는 로그를 남기고 버림
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger("studylens.api")

ENDPOINTS = {
    "start": ("study/start/", "start_time"),
    "end": ("study/end/", "end_time"),
    "distraction_start": ("study/distraction/start/", "start_time"),
    "distraction_end": ("study/distraction/end/", "end_time"),
    "away_start": ("study/distraction/start/", "start_time"),
    "away_end": ("study/distraction/end/", "end_time"),
    "capture": ("image/upload/", "captured_at"),
}


# 딴짓 이벤트 → 서버 reason
REASONS = {
    "distraction_start": "phone",
    "distraction_end": "phone",
    "away_start": "away",
    "away_end": "away",
}


class AuthError(Exception):
    """아이디/비밀번호가 틀린 경우 (재시도해도 소용없음)."""


def to_iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


class StudyLensClient:
    def __init__(self, base_url, username, password, queue_dir, *,
                 timeout=10, retry_base=2, retry_max=60, session=None):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.retry_base = retry_base
        self.retry_max = retry_max
        self.http = session or requests.Session()

        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)

        self._access = None
        self._refresh = None
        self._lock = threading.Lock()
        self._seq = self._max_seq() + 1
        self._wakeup = threading.Event()
        self._stop = threading.Event()
        self._thread = None

    # ==============================================================
    # 인증
    # ==============================================================
    def login(self):
        """로그인. 성공 True / 네트워크 문제 False / 계정 오류는 AuthError."""
        try:
            res = self.http.post(
                f"{self.base_url}/auth/login/",
                json={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            log.warning("로그인 요청 실패(네트워크): %s", e)
            return False
        if res.status_code == 200:
            body = res.json()
            self._access, self._refresh = body["access"], body.get("refresh")
            return True
        if res.status_code in (400, 401):
            raise AuthError("아이디 또는 비밀번호가 올바르지 않습니다.")
        log.warning("로그인 응답 오류: %s %s", res.status_code, res.text[:200])
        return False

    def _refresh_token(self):
        if not self._refresh:
            return False
        try:
            res = self.http.post(f"{self.base_url}/auth/refresh/", json={"refresh": self._refresh}, timeout=self.timeout)
        except requests.RequestException:
            return False
        if res.status_code == 200:
            self._access = res.json()["access"]
            return True
        return False

    def _authorized_post(self, path, **kwargs):
        """POST + 401이면 토큰 갱신 후 1회 재시도."""
        if self._access is None and not self.login():
            raise requests.ConnectionError("로그인 불가")

        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self._access}"}
            # 파일 업로드 재시도를 위해 파일 포인터를 처음으로
            for f in (kwargs.get("files") or {}).values():
                f[1].seek(0)
            res = self.http.post(f"{self.base_url}/{path}", headers=headers, timeout=self.timeout, **kwargs)
            if res.status_code != 401 or attempt == 1:
                return res
            log.info("액세스 토큰 만료 → 갱신 시도")
            if not (self._refresh_token() or self.login()):
                return res
        return res

    # ==============================================================
    # 디스크 큐
    # ==============================================================
    def _max_seq(self):
        seqs = [int(p.stem) for p in self.queue_dir.glob("*.json") if p.stem.isdigit()]
        return max(seqs, default=0)

    def _pending(self):
        return sorted(p for p in self.queue_dir.glob("*.json") if p.stem.isdigit())

    def pending_count(self):
        return len(self._pending())

    def enqueue(self, kind, event_time, image_bytes=None):
        """이벤트를 디스크 큐에 저장 (원자적 쓰기) 하고 전송 스레드를 깨운다."""
        if kind not in ENDPOINTS:
            raise ValueError(kind)
        with self._lock:
            seq = self._seq
            self._seq += 1
        name = f"{seq:012d}"
        item = {"kind": kind, "time": event_time, "image": None}
        if image_bytes is not None:
            img_path = self.queue_dir / f"{name}.jpg"
            img_path.write_bytes(image_bytes)
            item["image"] = img_path.name
        tmp = self.queue_dir / f"{name}.tmp"
        tmp.write_text(json.dumps(item), encoding="utf-8")
        os.replace(tmp, self.queue_dir / f"{name}.json")
        self._wakeup.set()

    def _remove(self, path, item):
        if item.get("image"):
            (self.queue_dir / item["image"]).unlink(missing_ok=True)
        path.unlink(missing_ok=True)

    def _send(self, item):
        """반환: 'ok' | 'drop' | 'retry'"""
        path, time_field = ENDPOINTS[item["kind"]]
        stamp = to_iso(item["time"])
        try:
            if item["kind"] == "capture":
                img_path = self.queue_dir / (item.get("image") or "")
                if not img_path.is_file():
                    return "drop"
                with open(img_path, "rb") as fh:
                    res = self._authorized_post(
                        path,
                        files={"image": ("study.jpg", fh, "image/jpeg")},
                        data={time_field: stamp},
                    )
            else:
                payload = {time_field: stamp}
                if item["kind"] in REASONS:
                    payload["reason"] = REASONS[item["kind"]]
                res = self._authorized_post(path, json=payload)
        except AuthError:
            raise
        except requests.RequestException as e:
            log.warning("전송 실패(%s): %s", item["kind"], e)
            return "retry"

        if 200 <= res.status_code < 300:
            return "ok"
        if res.status_code in (400, 404, 413):
            log.warning("서버가 이벤트를 거절해 버립니다 (%s %s): %s", item["kind"], res.status_code, res.text[:200])
            return "drop"
        log.warning("서버 오류(%s %s) → 재시도 예정", item["kind"], res.status_code)
        return "retry"

    def flush_once(self):
        """큐를 순서대로 전송. 전송 실패가 나면 그 지점에서 멈추고 False."""
        for path in self._pending():
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                log.warning("손상된 큐 파일 삭제: %s", path.name)
                path.unlink(missing_ok=True)
                continue
            result = self._send(item)
            if result == "retry":
                return False
            if result == "ok":
                log.info("전송 완료: %s", item["kind"])
            self._remove(path, item)
        return True

    # ==============================================================
    # 백그라운드 전송 스레드
    # ==============================================================
    def start_worker(self):
        self._thread = threading.Thread(target=self._run, name="studylens-uploader", daemon=True)
        self._thread.start()

    def _run(self):
        delay = self.retry_base
        while not self._stop.is_set():
            try:
                ok = self.flush_once()
            except AuthError as e:
                log.error("인증 오류로 전송 중단: %s", e)
                return
            except Exception:  # 스레드가 죽지 않도록
                log.exception("전송 스레드 예외")
                ok = False
            if ok:
                delay = self.retry_base
                self._wakeup.wait()
                self._wakeup.clear()
            else:
                log.info("%d초 후 재전송 (대기 %d건)", delay, self.pending_count())
                self._stop.wait(delay)
                delay = min(delay * 2, self.retry_max)

    def stop_worker(self, flush_timeout=10):
        """남은 큐를 최대 flush_timeout 초 동안 전송 시도 후 종료. 못 보낸 건은 다음 실행 때 전송."""
        deadline = time.time() + flush_timeout
        while self.pending_count() and time.time() < deadline:
            self._wakeup.set()
            time.sleep(0.2)
        self._stop.set()
        self._wakeup.set()
        if self._thread:
            self._thread.join(timeout=2)
        return self.pending_count()
