from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import DistractionInterval, StudySession, UserProfile
from .reports import build_report, focus_segments, hourly_distribution

PW = "Study-pass-2026!"


def kst(y, m, d, hh=0, mm=0):
    return timezone.make_aware(datetime(y, m, d, hh, mm), timezone.get_current_timezone())


class ReportLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reporter", password=PW)
        UserProfile.objects.create(user=self.user, daily_goal_minutes=60)

    def session(self, start, end, distractions=()):
        s = StudySession.objects.create(user=self.user, start_time=start, end_time=end)
        for reason, ds, de in distractions:
            DistractionInterval.objects.create(session=s, reason=reason, start_time=ds, end_time=de)
        return s

    def report(self, start=date(2026, 3, 2), end=date(2026, 3, 8), now=None):
        return build_report(self.user, "custom", start, end, now=now or kst(2026, 3, 9, 12))

    def test_focus_segments_and_deep_focus(self):
        # 21:00~22:30 세션, 21:40~21:45 휴대폰 → 40분 + 45분 두 구간 모두 25분 이상
        self.session(kst(2026, 3, 3, 21), kst(2026, 3, 3, 22, 30), [
            ("phone", kst(2026, 3, 3, 21, 40), kst(2026, 3, 3, 21, 45)),
        ])
        # 10:00~10:40, 10:20~10:30 자리 이탈 → 20분 + 10분 (25분 미만)
        self.session(kst(2026, 3, 4, 10), kst(2026, 3, 4, 10, 40), [
            ("away", kst(2026, 3, 4, 10, 20), kst(2026, 3, 4, 10, 30)),
        ])
        r = self.report()
        self.assertEqual(r["deep_focus"]["count"], 2)
        self.assertEqual(r["deep_focus"]["longest_seconds"], 45 * 60)
        self.assertEqual([b["minutes"] for b in r["deep_focus"]["blocks"]], [45, 40])
        self.assertEqual(r["totals"]["focus_seconds"], 85 * 60 + 30 * 60)

    def test_best_hours_and_time_band(self):
        self.session(kst(2026, 3, 3, 21), kst(2026, 3, 3, 22, 30))   # 21시 60분, 22시 30분
        self.session(kst(2026, 3, 4, 9), kst(2026, 3, 4, 9, 20))     # 9시 20분
        r = self.report()
        self.assertEqual(r["best_hours"][0]["hour"], 21)
        self.assertEqual(r["best_hours"][0]["label"], "21시~22시")
        self.assertEqual([h["hour"] for h in r["best_hours"]], [21, 22, 9])
        self.assertEqual(r["best_time_band"]["name"], "evening")
        self.assertEqual(sum(h["focus_seconds"] for h in r["hourly"]), 110 * 60)
        self.assertTrue(any("21시~22시" in s for s in r["insights"]))

    def test_away_and_phone_frequency(self):
        self.session(kst(2026, 3, 5, 14), kst(2026, 3, 5, 16), [
            ("away", kst(2026, 3, 5, 14, 30), kst(2026, 3, 5, 14, 35)),
            ("away", kst(2026, 3, 5, 15, 0), kst(2026, 3, 5, 15, 2)),
            ("away", kst(2026, 3, 5, 15, 10), kst(2026, 3, 5, 15, 10)),  # 취소된 구간(길이 0)
            ("phone", kst(2026, 3, 5, 15, 30), kst(2026, 3, 5, 15, 40)),
        ])
        r = self.report()
        self.assertEqual(r["away"]["count"], 2)
        self.assertEqual(r["away"]["total_seconds"], 7 * 60)
        self.assertEqual(r["away"]["per_hour"], 1.0)
        self.assertEqual(r["phone"]["count"], 1)
        day = next(d for d in r["daily"] if d["date"] == "2026-03-05")
        self.assertEqual((day["away_count"], day["phone_count"]), (2, 1))

    def test_goal_comparison_and_streak(self):
        # 이전 주(2/23~3/1) 순공부 60분, 이번 주 3/6~3/8 매일 90분 → 목표 3일 달성, +350%
        self.session(kst(2026, 2, 25, 9), kst(2026, 2, 25, 10))
        for d in (6, 7, 8):
            self.session(kst(2026, 3, d, 9), kst(2026, 3, d, 10, 30))
        r = self.report(now=kst(2026, 3, 8, 20))
        self.assertEqual(r["goal"]["achieved_days"], 3)
        self.assertEqual(r["goal"]["days"], 7)
        self.assertEqual(r["comparison"]["previous_focus_seconds"], 3600)
        self.assertEqual(r["comparison"]["change_rate"], 350.0)
        self.assertEqual(r["streak"]["current_days"], 3)
        self.assertEqual(r["streak"]["goal_current_days"], 3)

    def test_streak_ignores_empty_today(self):
        for d in (6, 7):
            self.session(kst(2026, 3, d, 9), kst(2026, 3, d, 10))
        r = self.report(now=kst(2026, 3, 8, 8))   # 3/8 아침, 아직 공부 전
        self.assertEqual(r["streak"]["current_days"], 2)

    def test_empty_report(self):
        r = self.report()
        self.assertEqual(r["totals"]["total_seconds"], 0)
        self.assertEqual(r["best_hours"], [])
        self.assertIsNone(r["best_time_band"])
        self.assertIsNone(r["away"]["per_hour"])
        self.assertEqual(len(r["insights"]), 1)

    def test_hourly_split_across_hours(self):
        segs = [(kst(2026, 3, 1, 23, 50), kst(2026, 3, 2, 0, 10))]
        h = hourly_distribution(segs)
        self.assertEqual((h[23], h[0]), (600, 600))

    def test_overlapping_distractions_merged_in_segments(self):
        sessions = [(1, kst(2026, 3, 1, 9), kst(2026, 3, 1, 10))]
        by_session = {1: [("phone", kst(2026, 3, 1, 9, 10), kst(2026, 3, 1, 9, 30)),
                          ("away", kst(2026, 3, 1, 9, 20), kst(2026, 3, 1, 9, 40))]}
        segs = focus_segments(sessions, by_session)
        self.assertEqual([(s.minute, e.minute) for s, e in segs], [(0, 10), (40, 0)])


class ReportAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("api_user", password=PW)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        now = timezone.now()
        StudySession.objects.create(user=self.user, start_time=now - timedelta(minutes=40), end_time=now)

    def test_summary(self):
        res = self.api.get("/api/study/summary/?period=week")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["daily"]), 7)
        self.assertIn("achieved_days", res.data["goal"])
        self.assertGreater(res.data["totals"]["focus_seconds"], 0)

    def test_report_and_validation(self):
        for q in ("", "?period=today", "?period=month", "?start=2026-01-01&end=2026-01-31"):
            res = self.api.get(f"/api/study/report/{q}")
            self.assertEqual(res.status_code, 200, q)
            for key in ("hourly", "best_hours", "deep_focus", "away", "phone", "comparison", "streak", "insights"):
                self.assertIn(key, res.data)
            self.assertEqual(len(res.data["hourly"]), 24)

        for q in ("?period=year", "?start=2026-01-01&end=2026-06-01", "?start=2026-02-01&end=2026-01-01", "?start=x&end=y"):
            self.assertEqual(self.api.get(f"/api/study/report/{q}").status_code, 400, q)

    def test_requires_auth(self):
        self.assertEqual(APIClient().get("/api/study/report/").status_code, 401)
