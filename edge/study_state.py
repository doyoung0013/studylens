"""
공부 상태 판정 상태머신.

카메라/모델/네트워크와 분리된 순수 로직이라 단위 테스트가 가능하다.
매 추론 결과를 observe() 로 넣으면, 서버로 보내야 할 이벤트 목록을 돌려준다.

판정 규칙
- 다수결: 최근 VOTE_WINDOW_SEC 동안의 프레임 중 VOTE_RATIO 이상 감지돼야 '있음'
- 시작: 사람 + (책 또는 노트북)이 MIN_STUDY_DETECTION_SEC 이상 연속으로 '있음'
        → 시작 시각은 연속 감지가 시작된 시각
- 종료: 사람이 PERSON_ABSENT_SEC 이상 없음  또는  책/노트북이 STUDY_OBJECT_MEMORY_SEC 이상 없음
        → 종료 시각은 '마지막으로 공부가 확인된 시각' (유예 시간은 공부 시간에서 제외)
- 딴짓: 공부 중 휴대폰이 PHONE_MIN_SEC 이상 연속 '있음' → 시작 / PHONE_CLEAR_SEC 이상 없음 → 종료
- 캡처: 공부 시작 직후 1장 + CAPTURE_INTERVAL_SEC 마다 1장
"""
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Event:
    kind: str          # "start" | "end" | "distraction_start" | "distraction_end" | "capture"
    time: float        # epoch seconds


@dataclass
class StateConfig:
    vote_window_sec: float = 1.5
    vote_ratio: float = 0.5
    min_study_detection_sec: float = 3
    person_absent_sec: float = 120
    study_object_memory_sec: float = 180
    phone_min_sec: float = 5
    phone_clear_sec: float = 5
    capture_interval_sec: float = 60

    @classmethod
    def from_module(cls, cfg):
        return cls(
            vote_window_sec=cfg.VOTE_WINDOW_SEC,
            vote_ratio=cfg.VOTE_RATIO,
            min_study_detection_sec=cfg.MIN_STUDY_DETECTION_SEC,
            person_absent_sec=cfg.PERSON_ABSENT_SEC,
            study_object_memory_sec=cfg.STUDY_OBJECT_MEMORY_SEC,
            phone_min_sec=cfg.PHONE_MIN_SEC,
            phone_clear_sec=cfg.PHONE_CLEAR_SEC,
            capture_interval_sec=cfg.CAPTURE_INTERVAL_SEC,
        )


@dataclass
class StudyStateMachine:
    config: StateConfig = field(default_factory=StateConfig)

    studying: bool = False
    distracted: bool = False

    _window: deque = field(default_factory=deque)
    _both_since: float = None          # 사람+공부물체가 연속으로 보이기 시작한 시각
    _last_person: float = None
    _last_object: float = None
    _phone_since: float = None         # 휴대폰이 연속으로 보이기 시작한 시각
    _last_phone: float = None
    _last_capture: float = None

    # --------------------------------------------------------------
    def _vote(self, now, person, study_object, phone):
        """최근 윈도 다수결로 (person, study_object, phone) 평활화."""
        self._window.append((now, person, study_object, phone))
        while self._window and now - self._window[0][0] > self.config.vote_window_sec:
            self._window.popleft()
        n = len(self._window)
        ratio = self.config.vote_ratio
        return tuple(sum(item[i] for item in self._window) / n >= ratio for i in (1, 2, 3))

    def observe(self, now, person, study_object, phone=False):
        """추론 결과 1회 반영. 발생한 이벤트 목록을 반환."""
        cfg = self.config
        events = []
        person, study_object, phone = self._vote(now, bool(person), bool(study_object), bool(phone))

        if person:
            self._last_person = now
        if study_object:
            self._last_object = now

        if person and study_object:
            if self._both_since is None:
                self._both_since = now
        else:
            self._both_since = None

        # ---------------- 시작 ----------------
        if not self.studying:
            if self._both_since is not None and now - self._both_since >= cfg.min_study_detection_sec:
                self.studying = True
                self._reset_phone()
                events.append(Event("start", self._both_since))
                events.append(Event("capture", now))
                self._last_capture = now
            return events

        # ---------------- 종료 ----------------
        person_gone = now - self._last_person >= cfg.person_absent_sec
        object_gone = now - self._last_object >= cfg.study_object_memory_sec
        if person_gone or object_gone:
            end_time = min(self._last_person, self._last_object)
            if self.distracted:
                events.append(Event("distraction_end", min(self._last_phone, end_time)))
            events.append(Event("end", end_time))
            self.studying = False
            self._both_since = None
            self._reset_phone()
            return events

        # ---------------- 딴짓 ----------------
        if phone:
            self._last_phone = now
            if self._phone_since is None:
                self._phone_since = now
            if not self.distracted and now - self._phone_since >= cfg.phone_min_sec:
                self.distracted = True
                events.append(Event("distraction_start", self._phone_since))
        else:
            self._phone_since = None
            if self.distracted and now - self._last_phone >= cfg.phone_clear_sec:
                self.distracted = False
                events.append(Event("distraction_end", self._last_phone))

        # ---------------- 캡처 ----------------
        if now - self._last_capture >= cfg.capture_interval_sec:
            events.append(Event("capture", now))
            self._last_capture = now

        return events

    def shutdown(self, now):
        """프로그램 종료 시 열린 구간을 닫는 이벤트."""
        events = []
        if self.studying:
            last_seen = min(x for x in (self._last_person, self._last_object, now) if x is not None)
            if self.distracted:
                events.append(Event("distraction_end", min(self._last_phone, last_seen)))
            events.append(Event("end", last_seen))
        self.studying = False
        self._reset_phone()
        return events

    def _reset_phone(self):
        self.distracted = False
        self._phone_since = None
        self._last_phone = None
