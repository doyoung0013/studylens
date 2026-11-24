import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from study_state import StateConfig, StudyStateMachine  # noqa: E402

FPS = 4
DT = 1 / FPS


SEATED = (0.5, 0.6, 0.4, 0.7)      # 화면 가운데 앉은 자세
STANDING = (0.85, 0.3, 0.3, 0.9)   # 옆으로 크게 벗어남


def run(sm, start, seconds, person, obj, phone=False, box=None):
    """start 부터 seconds 동안 같은 관측을 FPS 로 넣고 (이벤트 목록, 마지막 시각) 반환."""
    events = []
    t = start
    if box is None and person:
        box = SEATED
    for _ in range(int(seconds * FPS)):
        t += DT
        events += sm.observe(t, person, obj, phone, box if person else None)
    return events, t


def kinds(events):
    return [e.kind for e in events]


class StudyStateTest(unittest.TestCase):
    def setUp(self):
        self.cfg = StateConfig(
            min_study_detection_sec=3, person_absent_sec=120, study_object_memory_sec=180,
            phone_min_sec=5, phone_clear_sec=5, capture_interval_sec=60,
        )
        self.sm = StudyStateMachine(self.cfg)

    def test_start_requires_continuous_detection(self):
        events, t = run(self.sm, 0, 2, True, True)
        self.assertEqual(events, [])
        events, t = run(self.sm, t, 2, True, True)
        self.assertEqual(kinds(events), ["start", "capture"])
        # 시작 시각은 연속 감지가 시작된 시점
        self.assertAlmostEqual(events[0].time, DT, places=5)

    def test_intermittent_book_detection_still_starts(self):
        """책이 가끔만 잡혀도(가림·각도) 최근 10초 안에 보였으면 시작."""
        events = []
        t = 0.0
        for i in range(int(6 * FPS)):
            t += DT
            book = i % 12 == 0          # 3초에 한 번만 책 감지
            events += self.sm.observe(t, True, book)
        self.assertIn("start", kinds(events))

    def test_old_book_detection_does_not_start(self):
        """책이 보인 지 10초가 넘었으면 사람만 있어도 시작하지 않음."""
        self.sm.observe(0.1, False, True)
        events, _ = run(self.sm, 11, 10, True, False)
        self.assertEqual(events, [])

    def test_person_without_book_does_not_start(self):
        events, _ = run(self.sm, 0, 30, True, False)
        self.assertEqual(events, [])

    def test_single_frame_glitch_ignored(self):
        run(self.sm, 0, 5, True, True)
        # 한 프레임만 사람 미감지 → 다수결로 무시, 종료 안 됨
        t = 5.0
        self.assertEqual(self.sm.observe(t + DT, False, True), [])
        self.assertTrue(self.sm.studying)

    def test_end_when_person_leaves_uses_last_seen_time(self):
        _, t = run(self.sm, 0, 10, True, True)
        last_seen = t
        events, t = run(self.sm, t, 125, False, True)
        self.assertIn("end", kinds(events))
        end = [e for e in events if e.kind == "end"][0]
        # 다수결 윈도 때문에 약간 늦을 수 있지만 유예 시간(120초)은 포함되지 않아야 함
        self.assertLess(end.time - last_seen, 2)
        self.assertFalse(self.sm.studying)

    def test_end_when_book_gone_for_memory_sec(self):
        _, t = run(self.sm, 0, 10, True, True)
        events, t = run(self.sm, t, 170, True, False)
        self.assertNotIn("end", kinds(events))
        events, t = run(self.sm, t, 15, True, False)
        self.assertIn("end", kinds(events))

    def test_periodic_capture(self):
        events, _ = run(self.sm, 0, 3 + 125, True, True)
        self.assertEqual(kinds(events).count("capture"), 3)  # 시작 1 + 60초마다 2

    def test_phone_distraction(self):
        _, t = run(self.sm, 0, 5, True, True)
        events, t = run(self.sm, t, 3, True, True, phone=True)
        self.assertNotIn("distraction_start", kinds(events))
        events, t = run(self.sm, t, 4, True, True, phone=True)
        self.assertIn("distraction_start", kinds(events))
        self.assertTrue(self.sm.distracted)
        events, t = run(self.sm, t, 6, True, True, phone=False)
        self.assertIn("distraction_end", kinds(events))
        self.assertFalse(self.sm.distracted)

    def test_phone_ignored_when_not_studying(self):
        events, _ = run(self.sm, 0, 10, True, False, phone=True)
        self.assertEqual(events, [])

    def test_end_closes_distraction_first(self):
        _, t = run(self.sm, 0, 5, True, True)
        _, t = run(self.sm, t, 7, True, True, phone=True)
        self.assertTrue(self.sm.distracted)
        events, _ = run(self.sm, t, 125, False, False, phone=False)
        k = kinds(events)
        self.assertLess(k.index("distraction_end"), k.index("end"))

    # ---------------- 자리 이탈 ----------------
    def test_short_absence_is_away_not_end(self):
        _, t = run(self.sm, 0, 10, True, True)
        events, t = run(self.sm, t, 30, False, True)       # 30초 자리 비움 (종료 기준 120초 미만)
        self.assertEqual(kinds(events), ["away_start"])
        self.assertTrue(self.sm.away and self.sm.studying)
        away_start = events[0].time
        self.assertLess(away_start - 10, 1.5)               # 사라진 시점 기준
        events, t = run(self.sm, t, 5, True, True)
        self.assertEqual(kinds(events), ["away_end"])
        self.assertFalse(self.sm.away)

    def test_brief_absence_ignored(self):
        _, t = run(self.sm, 0, 10, True, True)
        events, t = run(self.sm, t, 5, False, True)         # 5초는 이탈 아님
        events2, _ = run(self.sm, t, 5, True, True)
        self.assertEqual(events + events2, [])

    def test_upper_body_displacement_is_away(self):
        _, t = run(self.sm, 0, 10, True, True, box=SEATED)
        events, t = run(self.sm, t, 15, True, True, box=STANDING)
        self.assertEqual(kinds(events), ["away_start"])
        events, t = run(self.sm, t, 5, True, True, box=SEATED)
        self.assertEqual(kinds(events), ["away_end"])

    def test_small_posture_change_not_away(self):
        _, t = run(self.sm, 0, 10, True, True, box=SEATED)
        events, _ = run(self.sm, t, 60, True, True, box=(0.6, 0.65, 0.4, 0.7))
        self.assertNotIn("away_start", kinds(events))

    def test_moved_seat_rebases_and_cancels_away(self):
        _, t = run(self.sm, 0, 10, True, True, box=SEATED)
        events, t = run(self.sm, t, 65, True, True, box=STANDING)   # 옆자리로 옮겨 계속 공부
        k = kinds(events)
        self.assertEqual(k.count("away_start"), 1)
        self.assertEqual(k.count("away_end"), 1)
        start = [e for e in events if e.kind == "away_start"][0]
        end = [e for e in events if e.kind == "away_end"][0]
        self.assertEqual(start.time, end.time)                        # 길이 0 → 구간 취소
        events, _ = run(self.sm, t, 30, True, True, box=STANDING)    # 새 기준점에서는 정상
        self.assertEqual(events, [])

    def test_no_capture_while_away(self):
        _, t = run(self.sm, 0, 10, True, True)
        events, _ = run(self.sm, t, 110, False, True)
        self.assertNotIn("capture", kinds(events))

    def test_session_end_closes_away_first(self):
        _, t = run(self.sm, 0, 10, True, True)
        events, _ = run(self.sm, t, 125, False, True)
        k = kinds(events)
        self.assertEqual(k, ["away_start", "away_end", "end"])

    def test_shutdown(self):
        self.assertEqual(self.sm.shutdown(100), [])
        _, t = run(self.sm, 0, 5, True, True)
        self.assertEqual(kinds(self.sm.shutdown(t + 1)), ["end"])
        self.assertFalse(self.sm.studying)


if __name__ == "__main__":
    unittest.main()
