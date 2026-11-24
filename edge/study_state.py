"""
공부 상태 판정 상태머신.

카메라/모델/네트워크와 분리된 순수 로직이라 단위 테스트가 가능하다.
매 추론 결과를 observe() 로 넣으면, 서버로 보내야 할 이벤트 목록을 돌려준다.

판정 규칙
- 다수결: 최근 VOTE_WINDOW_SEC 동안의 프레임 중 VOTE_RATIO 이상 감지돼야 '있음'
- 시작: 사람이 MIN_STUDY_DETECTION_SEC 이상 연속으로 '있음' + 책/노트북이 최근 OBJECT_START_MEMORY_SEC 안에 감지됨
        (YOLOv5 사전학습 모델은 책 인식이 불안정해서, 책은 매 프레임이 아니라 '최근에 한 번이라도'로 판단)
        → 시작 시각은 두 조건이 함께 성립하기 시작한 시각
- 종료: 사람이 PERSON_ABSENT_SEC 이상 없음  또는  책/노트북이 STUDY_OBJECT_MEMORY_SEC 이상 없음
        → 종료 시각은 '마지막으로 공부가 확인된 시각' (유예 시간은 공부 시간에서 제외)
- 딴짓: 공부 중 휴대폰이 PHONE_MIN_SEC 이상 연속 '있음' → 시작 / PHONE_CLEAR_SEC 이상 없음 → 종료
- 자리 이탈: 공부 중 사람이 안 보이거나, 상반신(사람 박스) 중심이 앉은 자세 기준점에서
        AWAY_MOVE_RATIO 이상 벗어난 상태가 AWAY_MIN_SEC 이상 → 시작 / AWAY_CLEAR_SEC 이상 복귀 → 종료
        위치만 다르고 계속 공부 중이면(자리를 옮겨 앉음) AWAY_REBASE_SEC 후 기준점을 다시 잡고 해당 구간을 취소
- 캡처: 공부 시작 직후 1장 + CAPTURE_INTERVAL_SEC 마다 1장 (자리 이탈 중 제외)
"""
import math
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Event:
    kind: str          # "start" | "end" | "distraction_start" | "distraction_end"
                       # | "away_start" | "away_end" | "capture"
    time: float        # epoch seconds


@dataclass
class StateConfig:
    vote_window_sec: float = 1.5
    vote_ratio: float = 0.5
    min_study_detection_sec: float = 3
    object_start_memory_sec: float = 10
    person_absent_sec: float = 120
    study_object_memory_sec: float = 180
    phone_min_sec: float = 5
    phone_clear_sec: float = 5
    away_min_sec: float = 10
    away_clear_sec: float = 3
    away_move_ratio: float = 0.25
    away_rebase_sec: float = 60
    baseline_alpha: float = 0.05
    capture_interval_sec: float = 60

    @classmethod
    def from_module(cls, cfg):
        return cls(
            vote_window_sec=cfg.VOTE_WINDOW_SEC,
            vote_ratio=cfg.VOTE_RATIO,
            min_study_detection_sec=cfg.MIN_STUDY_DETECTION_SEC,
            object_start_memory_sec=cfg.OBJECT_START_MEMORY_SEC,
            person_absent_sec=cfg.PERSON_ABSENT_SEC,
            study_object_memory_sec=cfg.STUDY_OBJECT_MEMORY_SEC,
            phone_min_sec=cfg.PHONE_MIN_SEC,
            phone_clear_sec=cfg.PHONE_CLEAR_SEC,
            away_min_sec=cfg.AWAY_MIN_SEC,
            away_clear_sec=cfg.AWAY_CLEAR_SEC,
            away_move_ratio=cfg.AWAY_MOVE_RATIO,
            away_rebase_sec=cfg.AWAY_REBASE_SEC,
            baseline_alpha=cfg.BASELINE_ALPHA,
            capture_interval_sec=cfg.CAPTURE_INTERVAL_SEC,
        )


@dataclass
class StudyStateMachine:
    config: StateConfig = field(default_factory=StateConfig)

    studying: bool = False
    distracted: bool = False
    away: bool = False

    _window: deque = field(default_factory=deque)
    _person_since: float = None        # 사람이 연속으로 보이기 시작한 시각
    _object_streak_start: float = None # 책/노트북이 '최근 감지' 상태가 된 시각
    _last_person: float = None
    _last_object: float = None
    _phone_since: float = None         # 휴대폰이 연속으로 보이기 시작한 시각
    _last_phone: float = None
    _last_capture: float = None
    _baseline: tuple = None            # 앉은 자세 기준점 (사람 박스 중심)
    _away_since: float = None          # 이탈 신호가 연속으로 시작된 시각
    _away_started: float = None        # 서버에 보낸 이탈 시작 시각
    _last_away_signal: float = None

    # --------------------------------------------------------------
    def _vote(self, now, person, study_object, phone):
        """최근 윈도 다수결로 (person, study_object, phone) 평활화."""
        self._window.append((now, person, study_object, phone))
        while self._window and now - self._window[0][0] > self.config.vote_window_sec:
            self._window.popleft()
        n = len(self._window)
        ratio = self.config.vote_ratio
        return tuple(sum(item[i] for item in self._window) / n >= ratio for i in (1, 2, 3))

    def observe(self, now, person, study_object, phone=False, person_box=None):
        """
        추론 결과 1회 반영. 발생한 이벤트 목록을 반환.
        person_box: (중심x, 중심y, 너비, 높이) 0~1 비율 — 자리 이탈(위치 변화) 판정용, 없으면 None
        """
        cfg = self.config
        events = []
        person, study_object, phone = self._vote(now, bool(person), bool(study_object), bool(phone))

        if person:
            self._last_person = now
            if self._person_since is None:
                self._person_since = now
        else:
            self._person_since = None

        if study_object:
            if self._last_object is None or now - self._last_object > cfg.object_start_memory_sec:
                self._object_streak_start = now
            self._last_object = now

        # ---------------- 시작 ----------------
        if not self.studying:
            object_recent = self._last_object is not None and now - self._last_object <= cfg.object_start_memory_sec
            if self._person_since is not None and object_recent:
                since = max(self._person_since, self._object_streak_start)
                if now - since >= cfg.min_study_detection_sec:
                    self.studying = True
                    self._reset_phone()
                    self._reset_away()
                    if person_box is not None:
                        self._baseline = (person_box[0], person_box[1])
                    events.append(Event("start", since))
                    events.append(Event("capture", now))
                    self._last_capture = now
            return events

        # ---------------- 종료 ----------------
        person_gone = now - self._last_person >= cfg.person_absent_sec
        object_gone = now - self._last_object >= cfg.study_object_memory_sec
        if person_gone or object_gone:
            end_time = min(self._last_person, self._last_object)
            events += self._close_open_intervals(end_time)
            events.append(Event("end", end_time))
            self.studying = False
            self._person_since = None
            self._reset_phone()
            self._reset_away()
            return events

        # ---------------- 자리 이탈 ----------------
        events += self._update_away(now, person, person_box)

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

        # ---------------- 캡처 (자리 이탈 중에는 빈 책상이므로 건너뜀) ----------------
        if not self.away and now - self._last_capture >= cfg.capture_interval_sec:
            events.append(Event("capture", now))
            self._last_capture = now

        return events

    def _update_away(self, now, person, person_box):
        cfg = self.config
        events = []

        displaced = False
        if person and person_box is not None:
            cx, cy = person_box[0], person_box[1]
            if self._baseline is None:
                self._baseline = (cx, cy)
            bx, by = self._baseline
            displaced = math.hypot(cx - bx, cy - by) > cfg.away_move_ratio
            if not displaced and not self.away:
                a = cfg.baseline_alpha  # 자세가 조금씩 바뀌는 건 기준점에 천천히 반영
                self._baseline = (bx + a * (cx - bx), by + a * (cy - by))

        if (not person) or displaced:
            self._last_away_signal = now
            if self._away_since is None:
                self._away_since = now
            if not self.away and now - self._away_since >= cfg.away_min_sec:
                self.away = True
                self._away_started = self._away_since
                events.append(Event("away_start", self._away_since))

            # 자리를 옮겨 앉은 경우: 사람·공부 물체는 보이는데 위치만 계속 다름 → 기준점 재설정 + 구간 취소
            object_recent = self._last_object is not None and now - self._last_object <= cfg.object_start_memory_sec
            if (self.away and displaced and object_recent
                    and now - self._away_since >= cfg.away_rebase_sec):
                self._baseline = (person_box[0], person_box[1])
                events.append(Event("away_end", self._away_started))  # 길이 0 구간 → 이탈 취소
                self.away = False
                self._away_since = None
        else:
            self._away_since = None
            if self.away and now - self._last_away_signal >= cfg.away_clear_sec:
                self.away = False
                events.append(Event("away_end", self._last_away_signal))
        return events

    def _close_open_intervals(self, end_time):
        events = []
        if self.distracted:
            events.append(Event("distraction_end", min(self._last_phone, end_time)))
        if self.away:
            events.append(Event("away_end", max(self._away_started, min(self._last_away_signal, end_time))))
        return events

    def shutdown(self, now):
        """프로그램 종료 시 열린 구간을 닫는 이벤트."""
        events = []
        if self.studying:
            last_seen = min(x for x in (self._last_person, self._last_object, now) if x is not None)
            events += self._close_open_intervals(last_seen)
            events.append(Event("end", last_seen))
        self.studying = False
        self._reset_phone()
        self._reset_away()
        return events

    def _reset_phone(self):
        self.distracted = False
        self._phone_since = None
        self._last_phone = None

    def _reset_away(self):
        self.away = False
        self._baseline = None
        self._away_since = None
        self._away_started = None
        self._last_away_signal = None
