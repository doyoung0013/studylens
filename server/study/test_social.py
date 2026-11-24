from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from .models import DistractionInterval, StudySession

PW = "Study-pass-2026!"


def study(user, minutes, distracted=0, ago_hours=1, open_=False):
    start = timezone.now() - timedelta(hours=ago_hours)
    s = StudySession.objects.create(
        user=user, start_time=start, end_time=None if open_ else start + timedelta(minutes=minutes)
    )
    if distracted:
        DistractionInterval.objects.create(session=s, start_time=start, end_time=start + timedelta(minutes=distracted))
    return s


class SignupTest(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def test_signup_returns_tokens_and_can_use_api(self):
        res = self.api.post("/api/auth/signup/", {"username": "new_user", "password": PW, "password2": PW}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertIn("access", res.data)
        self.assertTrue(User.objects.get(username="new_user").check_password(PW))

        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = self.api.get("/api/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "new_user")

    def test_signup_validation(self):
        User.objects.create_user("taken", password=PW)
        cases = [
            ({"username": "Taken", "password": PW, "password2": PW}, "이미 사용 중"),
            ({"username": "ab", "password": PW, "password2": PW}, "4~20자"),
            ({"username": "한글아이디", "password": PW, "password2": PW}, "4~20자"),
            ({"username": "gooduser", "password": PW, "password2": PW + "x"}, "일치하지"),
            ({"username": "gooduser", "password": "1234", "password2": "1234"}, None),
        ]
        for body, expected in cases:
            res = self.api.post("/api/auth/signup/", body, format="json")
            self.assertEqual(res.status_code, 400, body)
            if expected:
                self.assertIn(expected, res.data["detail"])
        self.assertFalse(User.objects.filter(username="gooduser").exists())

    def test_signup_throttled(self):
        rates = {"signup": "2/hour", "friend_request": "60/hour", "group_join": "30/hour"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
            codes = [
                self.api.post("/api/auth/signup/", {"username": f"user{i}x", "password": PW, "password2": PW},
                              format="json").status_code
                for i in range(3)
            ]
        self.assertEqual(codes, [201, 201, 429])

    def test_web_signup(self):
        res = self.client.post("/signup/", {"username": "webuser", "password": PW, "password2": PW})
        self.assertRedirects(res, "/dashboard/")
        res = self.client.get("/dashboard/")
        self.assertContains(res, "webuser")

        self.client.post("/logout/")
        res = self.client.post("/signup/", {"username": "webuser", "password": PW, "password2": PW})
        self.assertContains(res, "이미 사용 중")
