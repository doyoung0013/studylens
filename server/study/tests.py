import shutil
import tempfile
from datetime import date, datetime, timedelta
from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from .models import DistractionInterval, StudyImage, StudySession
from .services import daily_study_stats, local_day_bounds, sign_image

TEMP_MEDIA = tempfile.mkdtemp()


def kst(y, m, d, hh=0, mm=0, ss=0):
    return timezone.make_aware(datetime(y, m, d, hh, mm, ss), timezone.get_current_timezone())


def make_jpeg(size=(2000, 1500), fmt="JPEG"):
    buf = BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, format=fmt)
    return buf.getvalue()


class BaseAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", password="pw-for-tests-123")
        self.other = User.objects.create_user("other", password="pw-for-tests-123")
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)


# ------------------------------------------------------------------
# 집계 로직
# ------------------------------------------------------------------
class DailyStatsServiceTest(BaseAPITest):
    def test_no_minimum_correction(self):
        """과거의 '최소 3분' 임시 보정이 제거되었는지."""
        s = StudySession.objects.create(user=self.user, start_time=kst(2026, 3, 1, 10), end_time=kst(2026, 3, 1, 10, 0, 30))
        self.assertEqual(s.duration_seconds, 30)

    def test_session_split_at_midnight(self):
        StudySession.objects.create(user=self.user, start_time=kst(2026, 3, 1, 23, 30), end_time=kst(2026, 3, 2, 0, 45))
        stats = daily_study_stats(self.user, date(2026, 3, 1), date(2026, 3, 2), now=kst(2026, 3, 3))
        self.assertEqual([d["total_seconds"] for d in stats], [30 * 60, 45 * 60])

    def test_open_session_counted_until_now(self):
        StudySession.objects.create(user=self.user, start_time=kst(2026, 3, 1, 9))
        stats = daily_study_stats(self.user, date(2026, 3, 1), date(2026, 3, 1), now=kst(2026, 3, 1, 9, 20))
        self.assertEqual(stats[0]["total_seconds"], 20 * 60)

    def test_distraction_reduces_focus(self):
        s = StudySession.objects.create(user=self.user, start_time=kst(2026, 3, 1, 9), end_time=kst(2026, 3, 1, 10))
        DistractionInterval.objects.create(session=s, start_time=kst(2026, 3, 1, 9, 10), end_time=kst(2026, 3, 1, 9, 25))
        stat = daily_study_stats(self.user, date(2026, 3, 1), date(2026, 3, 1), now=kst(2026, 3, 2))[0]
        self.assertEqual(stat["total_seconds"], 3600)
        self.assertEqual(stat["distracted_seconds"], 900)
        self.assertEqual(stat["focus_seconds"], 2700)
        self.assertEqual(stat["focus_rate"], 75.0)

    def test_empty_days_and_other_users_excluded(self):
        StudySession.objects.create(user=self.other, start_time=kst(2026, 3, 1, 9), end_time=kst(2026, 3, 1, 10))
        stats = daily_study_stats(self.user, date(2026, 3, 1), date(2026, 3, 3), now=kst(2026, 3, 4))
        self.assertEqual(len(stats), 3)
        self.assertTrue(all(d["total_seconds"] == 0 and d["focus_rate"] is None for d in stats))


# ------------------------------------------------------------------
# 세션 API
# ------------------------------------------------------------------
class StudySessionAPITest(BaseAPITest):
    def test_requires_auth(self):
        res = APIClient().post("/api/study/start/")
        self.assertEqual(res.status_code, 401)

    def test_start_and_end_with_end_time(self):
        res = self.client_api.post("/api/study/start/")
        self.assertEqual(res.status_code, 201)
        session = StudySession.objects.get(id=res.data["session"]["id"])

        end_time = session.start_time + timedelta(minutes=5)
        with mock.patch("django.utils.timezone.now", return_value=session.start_time + timedelta(minutes=8)):
            res = self.client_api.post("/api/study/end/", {"end_time": end_time.isoformat()}, format="json")
        self.assertEqual(res.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.end_time, end_time)
        self.assertEqual(session.duration_seconds, 300)

    def test_end_time_clamped(self):
        self.client_api.post("/api/study/start/")
        session = StudySession.objects.get()
        # 시작보다 이전 시각 → 시작 시각으로 보정
        before = session.start_time - timedelta(minutes=1)
        self.client_api.post("/api/study/end/", {"end_time": before.isoformat()}, format="json")
        session.refresh_from_db()
        self.assertEqual(session.end_time, session.start_time)

    def test_end_without_session(self):
        res = self.client_api.post("/api/study/end/")
        self.assertEqual(res.status_code, 400)

    def test_invalid_and_too_old_time(self):
        res = self.client_api.post("/api/study/start/", {"start_time": "어제"}, format="json")
        self.assertEqual(res.status_code, 400)
        old = timezone.now() - timedelta(days=3)
        res = self.client_api.post("/api/study/start/", {"start_time": old.isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_stale_session_closed_at_last_activity(self):
        start = timezone.now() - timedelta(hours=2)
        stale = StudySession.objects.create(user=self.user, start_time=start)
        StudyImage.objects.create(user=self.user, session=stale, image="x.jpg", captured_at=start + timedelta(minutes=30))

        res = self.client_api.post("/api/study/start/")
        self.assertEqual(res.status_code, 201)
        self.assertIn("closed_stale_session", res.data)
        stale.refresh_from_db()
        self.assertEqual(stale.end_time, start + timedelta(minutes=30))
        self.assertEqual(StudySession.objects.filter(user=self.user, end_time__isnull=True).count(), 1)


# ------------------------------------------------------------------
# 딴짓 & 실시간 상태
# ------------------------------------------------------------------
class DistractionAndCurrentAPITest(BaseAPITest):
    def test_distraction_flow_and_current(self):
        res = self.client_api.get("/api/study/current/")
        self.assertFalse(res.data["studying"])
        self.assertIsNone(res.data["session"])

        start = timezone.now() - timedelta(minutes=42)
        self.client_api.post("/api/study/start/", {"start_time": start.isoformat()}, format="json")

        d_start = start + timedelta(minutes=10)
        res = self.client_api.post("/api/study/distraction/start/", {"start_time": d_start.isoformat()}, format="json")
        self.assertEqual(res.status_code, 201)
        # 중복 start → 기존 구간 반환
        res = self.client_api.post("/api/study/distraction/start/")
        self.assertEqual(res.status_code, 200)

        res = self.client_api.get("/api/study/current/")
        self.assertTrue(res.data["studying"])
        self.assertTrue(res.data["session"]["is_distracted"])
        self.assertGreaterEqual(res.data["session"]["elapsed_seconds"], 42 * 60)

        res = self.client_api.post(
            "/api/study/distraction/end/", {"end_time": (d_start + timedelta(minutes=6)).isoformat()}, format="json"
        )
        self.assertEqual(res.status_code, 200)

        res = self.client_api.get("/api/study/current/")
        session = res.data["session"]
        self.assertFalse(session["is_distracted"])
        self.assertEqual(session["distracted_seconds"], 6 * 60)
        self.assertEqual(session["focus_seconds"], session["elapsed_seconds"] - 360)
        self.assertEqual(res.data["today"]["distracted_seconds"] <= res.data["today"]["total_seconds"], True)

    def test_phone_and_away_overlap_counted_once(self):
        start = timezone.now() - timedelta(minutes=60)
        self.client_api.post("/api/study/start/", {"start_time": start.isoformat()}, format="json")
        post = lambda url, **body: self.client_api.post(url, {k: v.isoformat() if hasattr(v, "isoformat") else v
                                                              for k, v in body.items()}, format="json")
        # 휴대폰 10~20분, 자리 이탈 15~25분 → 합집합 15분
        self.assertEqual(post("/api/study/distraction/start/", start_time=start + timedelta(minutes=10)).status_code, 201)
        self.assertEqual(post("/api/study/distraction/start/", start_time=start + timedelta(minutes=15),
                              reason="away").status_code, 201)
        res = self.client_api.get("/api/study/current/")
        self.assertTrue(res.data["session"]["is_away"])
        self.assertTrue(res.data["session"]["is_on_phone"])

        post("/api/study/distraction/end/", end_time=start + timedelta(minutes=20), reason="phone")
        post("/api/study/distraction/end/", end_time=start + timedelta(minutes=25), reason="away")
        session = self.client_api.get("/api/study/current/").data["session"]
        self.assertEqual(session["distracted_seconds"], 15 * 60)
        self.assertFalse(session["is_distracted"])

        today = self.client_api.get("/api/stats/daily/?days=1").data[-1]
        self.assertGreaterEqual(today["distracted_seconds"], 0)
        self.assertLessEqual(today["distracted_seconds"], 15 * 60)

    def test_unknown_reason_rejected(self):
        self.client_api.post("/api/study/start/")
        self.assertEqual(self.client_api.post("/api/study/distraction/start/", {"reason": "sleep"},
                                              format="json").status_code, 400)

    def test_distraction_requires_session(self):
        res = self.client_api.post("/api/study/distraction/start/")
        self.assertEqual(res.status_code, 400)
        res = self.client_api.post("/api/study/distraction/end/")
        self.assertEqual(res.status_code, 400)

    def test_session_end_closes_open_distraction(self):
        self.client_api.post("/api/study/start/")
        self.client_api.post("/api/study/distraction/start/")
        self.client_api.post("/api/study/end/")
        self.assertFalse(DistractionInterval.objects.filter(end_time__isnull=True).exists())


# ------------------------------------------------------------------
# 통계 & 갤러리 API
# ------------------------------------------------------------------
class StatsAndGalleryAPITest(BaseAPITest):
    def test_stats_days_and_range(self):
        res = self.client_api.get("/api/stats/daily/?days=7")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 7)
        self.assertEqual(res.data[-1]["date"], timezone.localdate().isoformat())
        self.assertIn("focus_seconds", res.data[0])

        res = self.client_api.get("/api/stats/daily/?start=2026-02-01&end=2026-02-28")
        self.assertEqual(len(res.data), 28)

    def test_stats_validation(self):
        for q in ["days=abc", "days=0", "days=999", "start=2026-02-10&end=2026-02-01", "start=bad&end=2026-02-01"]:
            self.assertEqual(self.client_api.get(f"/api/stats/daily/?{q}").status_code, 400, q)

    def test_gallery_by_date_uses_captured_at(self):
        day = date(2026, 3, 1)
        start, _ = local_day_bounds(day)
        StudyImage.objects.create(user=self.user, image="a.jpg", captured_at=start + timedelta(hours=10))
        StudyImage.objects.create(user=self.user, image="b.jpg", captured_at=start + timedelta(days=1, hours=1))
        StudyImage.objects.create(user=self.other, image="c.jpg", captured_at=start + timedelta(hours=10))

        res = self.client_api.get("/api/gallery/?date=2026-03-01")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertIn("/api/images/", res.data[0]["image_url"])
        self.assertIn("token=", res.data[0]["image_url"])

        self.assertEqual(self.client_api.get("/api/gallery/?date=03-01").status_code, 400)
        self.assertEqual(self.client_api.get("/api/gallery/today/").status_code, 200)


# ------------------------------------------------------------------
# 이미지 업로드 & 서명 URL
# ------------------------------------------------------------------
@override_settings(MEDIA_ROOT=TEMP_MEDIA, STUDYLENS_MAX_IMAGE_SIDE=1280)
class ImageAPITest(BaseAPITest):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def upload(self, data, name="study.jpg", **extra):
        f = SimpleUploadedFile(name, data, content_type="image/jpeg")
        return self.client_api.post("/api/image/upload/", {"image": f, **extra}, format="multipart")

    def test_upload_resizes_and_attaches_open_session(self):
        self.client_api.post("/api/study/start/")
        res = self.upload(make_jpeg())
        self.assertEqual(res.status_code, 201)
        img = StudyImage.objects.get(id=res.data["id"])
        self.assertIsNotNone(img.session)
        with Image.open(img.image.path) as stored:
            self.assertEqual(max(stored.size), 1280)
            self.assertEqual(stored.format, "JPEG")

    def test_upload_rejects_non_image_and_large(self):
        self.assertEqual(self.upload(b"not an image").status_code, 400)
        with override_settings(STUDYLENS_MAX_IMAGE_BYTES=100):
            self.assertEqual(self.upload(make_jpeg((50, 50))).status_code, 400)

    def test_upload_other_users_session_rejected(self):
        s = StudySession.objects.create(user=self.other, start_time=timezone.now())
        self.assertEqual(self.upload(make_jpeg((50, 50)), session_id=s.id).status_code, 400)

    def test_signed_file_url(self):
        res = self.upload(make_jpeg((64, 48)))
        image_id = res.data["id"]
        anon = APIClient()

        ok = anon.get(res.data["image_url"])
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok["Content-Type"], "image/jpeg")

        self.assertEqual(anon.get(f"/api/images/{image_id}/file/").status_code, 404)
        self.assertEqual(anon.get(f"/api/images/{image_id}/file/?token=forged").status_code, 404)
        # 다른 이미지의 토큰은 재사용 불가
        self.assertEqual(anon.get(f"/api/images/{image_id}/file/?token={sign_image(image_id + 1)}").status_code, 404)

    def test_media_not_public(self):
        res = self.upload(make_jpeg((64, 48)))
        img = StudyImage.objects.get(id=res.data["id"])
        self.assertEqual(APIClient().get(img.image.url).status_code, 404)


# ------------------------------------------------------------------
# 웹 대시보드
# ------------------------------------------------------------------
class WebTest(BaseAPITest):
    def test_login_dashboard_logout(self):
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)
        res = self.client.post("/", {"username": "tester", "password": "pw-for-tests-123"})
        self.assertRedirects(res, "/dashboard/")

        StudySession.objects.create(user=self.user, start_time=timezone.now() - timedelta(minutes=42))
        res = self.client.get("/dashboard/")
        self.assertContains(res, "지금 공부 중")
        self.assertContains(res, "42분째")

        self.client.post("/logout/")
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)

    def test_login_failure(self):
        res = self.client.post("/", {"username": "tester", "password": "wrong"})
        self.assertContains(res, "올바르지 않습니다")
