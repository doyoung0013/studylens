import os
import sys
import tempfile
import unittest

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import AuthError, StudyLensClient  # noqa: E402


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


class FakeHTTP:
    """requests.Session 대역. responses 에 path → [응답 또는 예외] 를 순서대로 넣는다."""

    def __init__(self):
        self.calls = []
        self.responses = {}
        self.online = True

    def post(self, url, **kwargs):
        path = url.split("/api/", 1)[1]
        self.calls.append((path, kwargs))
        if not self.online:
            raise requests.ConnectionError("offline")
        queue = self.responses.get(path)
        if queue:
            r = queue.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        if path == "auth/login/":
            return FakeResponse(200, {"access": "a1", "refresh": "r1"})
        return FakeResponse(201, {})


class ApiClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.http = FakeHTTP()
        self.client = StudyLensClient("http://srv/api", "u", "p", self.tmp.name, session=self.http)

    def tearDown(self):
        self.tmp.cleanup()

    def paths(self):
        return [c[0] for c in self.http.calls]

    def test_wrong_password_raises(self):
        self.http.responses["auth/login/"] = [FakeResponse(401)]
        with self.assertRaises(AuthError):
            self.client.login()

    def test_events_sent_in_order_with_times(self):
        self.client.enqueue("start", 1000.0)
        self.client.enqueue("capture", 1001.0, b"\xff\xd8jpeg")
        self.client.enqueue("distraction_start", 1002.0)
        self.client.enqueue("distraction_end", 1003.0)
        self.client.enqueue("end", 1004.0)
        self.assertTrue(self.client.flush_once())
        self.assertEqual(self.paths(), [
            "auth/login/", "study/start/", "image/upload/",
            "study/distraction/start/", "study/distraction/end/", "study/end/",
        ])
        start_call = self.http.calls[1][1]
        self.assertIn("start_time", start_call["json"])
        self.assertTrue(start_call["json"]["start_time"].startswith("1970-01-01T00:16:40"))
        self.assertEqual(self.client.pending_count(), 0)
        self.assertEqual(os.listdir(self.tmp.name), [])  # 이미지 파일도 정리됨

    def test_offline_keeps_queue_and_survives_restart(self):
        self.http.online = False
        self.client.enqueue("start", 1000.0)
        self.client.enqueue("end", 1100.0)
        self.assertFalse(self.client.flush_once())
        self.assertEqual(self.client.pending_count(), 2)

        # 프로그램 재시작 (같은 큐 디렉터리)
        self.http.online = True
        restarted = StudyLensClient("http://srv/api", "u", "p", self.tmp.name, session=self.http)
        restarted.enqueue("start", 2000.0)
        self.assertTrue(restarted.flush_once())
        sent = [c for c in self.paths() if c.startswith("study/")]
        self.assertEqual(sent, ["study/start/", "study/end/", "study/start/"])

    def test_token_refresh_on_401(self):
        self.client.login()
        self.http.responses["study/start/"] = [FakeResponse(401), FakeResponse(201)]
        self.http.responses["auth/refresh/"] = [FakeResponse(200, {"access": "a2"})]
        self.client.enqueue("start", 1000.0)
        self.assertTrue(self.client.flush_once())
        self.assertEqual(self.paths(), ["auth/login/", "study/start/", "auth/refresh/", "study/start/"])
        self.assertEqual(self.http.calls[-1][1]["headers"]["Authorization"], "Bearer a2")

    def test_rejected_event_dropped_server_error_retried(self):
        self.http.responses["study/end/"] = [FakeResponse(400, {"detail": "진행 중인 세션이 없습니다."})]
        self.client.enqueue("end", 1000.0)
        self.assertTrue(self.client.flush_once())
        self.assertEqual(self.client.pending_count(), 0)

        self.http.responses["study/start/"] = [FakeResponse(500)]
        self.client.enqueue("start", 1000.0)
        self.assertFalse(self.client.flush_once())
        self.assertEqual(self.client.pending_count(), 1)
        self.assertTrue(self.client.flush_once())
        self.assertEqual(self.client.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
