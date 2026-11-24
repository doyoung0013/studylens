import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from study_state import StateConfig, StudyStateMachine  # noqa: E402

FPS = 4
DT = 1 / FPS


def run(sm, start, seconds, person, obj, phone=False):
    """start 부터 seconds 동안 같은 관측을 FPS 로 넣고 (이벤트 목록, 마지막 시각) 반환."""
    events = []
    t = start
    for _ in range(int(seconds * FPS)):
        t += DT
        events += sm.observe(t, person, obj, phone)
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

    def test_shutdown(self):
        self.assertEqual(self.sm.shutdown(100), [])
        _, t = run(self.sm, 0, 5, True, True)
        self.assertEqual(kinds(self.sm.shutdown(t + 1)), ["end"])
        self.assertFalse(self.sm.studying)


if __name__ == "__main__":
    unittest.main()
