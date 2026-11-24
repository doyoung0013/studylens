"""
학습 리포트 / 요약 계산.

- 집중이 잘 되는 시간대 (시간대별 순공부 분포)
- 25분 이상 연속 집중 구간 (딴짓·자리 이탈 없이 이어진 구간)
- 자리 이탈 / 휴대폰 사용 빈도
- 하루 목표 달성 현황, 연속 공부 일수, 이전 기간 대비 증감
"""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from .models import DistractionInterval, StudySession, UserProfile
from .services import (
    InvalidParam,
    daily_study_stats,
    focus_rate,
    local_day_bounds,
    merge_intervals,
    parse_date_param,
    period_range,
    totals_by_user,
)

DEEP_FOCUS_MIN_SEC = 25 * 60
STREAK_LOOKBACK_DAYS = 120
MAX_REPORT_DAYS = 92

TIME_BANDS = [
    ("dawn", "새벽 (0~6시)", range(0, 6)),
    ("morning", "오전 (6~12시)", range(6, 12)),
    ("afternoon", "오후 (12~18시)", range(12, 18)),
    ("evening", "저녁 (18~24시)", range(18, 24)),
]


# ------------------------------------------------------------------
# 기간 파라미터
# ------------------------------------------------------------------
def resolve_range(params, default_period="week"):
    """?period=today|week|month 또는 ?start=&end= → (period, start_date, end_date)"""
    if params.get("start") or params.get("end"):
        start = parse_date_param(params.get("start"), "start")
        end = parse_date_param(params.get("end"), "end")
        if end < start:
            raise InvalidParam("end는 start보다 같거나 이후여야 합니다.")
        if (end - start).days + 1 > MAX_REPORT_DAYS:
            raise InvalidParam(f"리포트 기간은 최대 {MAX_REPORT_DAYS}일입니다.")
        return "custom", start, end
    period = params.get("period", default_period)
    start, end = period_range(period)
    return period, start, end


# ------------------------------------------------------------------
# 구간 계산
# ------------------------------------------------------------------
def _sessions_with_distractions(user, range_start, range_end, now):
    """범위와 겹치는 세션 [(session_id, start, end)] 과 세션별 딴짓 구간 목록."""
    sessions = [
        (sid, max(s, range_start), min(e or now, range_end, now))
        for sid, s, e in (
            StudySession.objects
            .filter(user=user, start_time__lt=range_end)
            .exclude(end_time__isnull=False, end_time__lte=range_start)
            .values_list("id", "start_time", "end_time")
        )
    ]
    sessions = [(sid, s, e) for sid, s, e in sessions if e > s]

    rows = (
        DistractionInterval.objects
        .filter(session_id__in=[sid for sid, _, _ in sessions])
        .values_list("session_id", "reason", "start_time", "end_time")
    )
    by_session = defaultdict(list)
    for sid, reason, s, e in rows:
        by_session[sid].append((reason, s, e or now))
    return sessions, by_session


def focus_segments(sessions, by_session):
    """세션 구간에서 딴짓(합집합)을 빼고 남은 '순공부' 구간 목록."""
    segments = []
    for sid, s_start, s_end in sessions:
        cuts = merge_intervals(
            (max(s, s_start), min(e, s_end)) for _, s, e in by_session.get(sid, []) if min(e, s_end) > max(s, s_start)
        )
        cursor = s_start
        for c_start, c_end in cuts:
            if c_start > cursor:
                segments.append((cursor, c_start))
            cursor = max(cursor, c_end)
        if s_end > cursor:
            segments.append((cursor, s_end))
    return segments


def hourly_distribution(segments):
    """순공부 구간을 로컬 시각의 '시' 단위로 나눠 24칸 분포(초)를 만든다."""
    buckets = [0.0] * 24
    tz = timezone.get_current_timezone()
    for s, e in segments:
        cur = s
        while cur < e:
            local = timezone.localtime(cur, tz)
            next_hour = (local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            piece_end = min(e, next_hour)
            buckets[local.hour] += (piece_end - cur).total_seconds()
            cur = piece_end
    return [int(b) for b in buckets]


def _reason_stats(by_session, reason, range_start, range_end):
    count, seconds = 0, 0.0
    daily = defaultdict(int)
    for items in by_session.values():
        for r, s, e in items:
            if r != reason or not (range_start <= s < range_end):
                continue
            dur = (min(e, range_end) - s).total_seconds()
            if dur <= 0:  # 취소된(길이 0) 구간 제외
                continue
            count += 1
            seconds += dur
            daily[timezone.localtime(s).date().isoformat()] += 1
    return count, int(seconds), daily


def _streaks(user, end_date, goal_seconds, now):
    """end_date 까지 이어진 연속 공부 일수 / 연속 목표 달성 일수 (최근 120일 기준)."""
    start = end_date - timedelta(days=STREAK_LOOKBACK_DAYS - 1)
    days = daily_study_stats(user, start, end_date, now=now)

    # 오늘 아직 기록이 없으면 어제까지를 기준으로 센다
    if days and days[-1]["date"] == timezone.localdate(now).isoformat() and days[-1]["focus_seconds"] < 60:
        days = days[:-1]

    def count(cond):
        n = 0
        for d in reversed(days):
            if not cond(d):
                break
            n += 1
        return n

    return {
        "current_days": count(lambda d: d["focus_seconds"] >= 60),
        "goal_current_days": count(lambda d: d["focus_seconds"] >= goal_seconds),
    }


# ------------------------------------------------------------------
# 요약 / 리포트
# ------------------------------------------------------------------
def _totals(daily, goal_minutes):
    total = sum(d["total_seconds"] for d in daily)
    distracted = sum(d["distracted_seconds"] for d in daily)
    focus = total - distracted
    study_days = sum(1 for d in daily if d["total_seconds"] > 0)
    achieved = sum(1 for d in daily if d["goal_achieved"])
    return (
        {
            "total_seconds": total,
            "distracted_seconds": distracted,
            "focus_seconds": focus,
            "focus_rate": focus_rate(total, distracted),
            "study_days": study_days,
            "avg_focus_seconds_per_study_day": focus // study_days if study_days else 0,
        },
        {
            "daily_goal_minutes": goal_minutes,
            "achieved_days": achieved,
            "days": len(daily),
            "achievement_rate": round(100 * achieved / len(daily), 1) if daily else None,
        },
    )


def build_summary(user, period, start, end, now=None):
    now = now or timezone.now()
    goal_minutes = UserProfile.for_user(user).daily_goal_minutes
    daily = daily_study_stats(user, start, end, now=now)
    totals, goal = _totals(daily, goal_minutes)
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "totals": totals,
        "goal": goal,
        "daily": daily,
    }


def _hour_label(h):
    return f"{h:02d}시~{(h + 1) % 24:02d}시"


def build_report(user, period, start, end, now=None):
    now = now or timezone.now()
    report = build_summary(user, period, start, end, now=now)
    goal_seconds = report["goal"]["daily_goal_minutes"] * 60

    range_start, _ = local_day_bounds(start)
    _, range_end = local_day_bounds(end)
    sessions, by_session = _sessions_with_distractions(user, range_start, range_end, now)
    segments = focus_segments(sessions, by_session)

    # ---------- 집중 시간대 ----------
    hourly = hourly_distribution(segments)
    best_hours = [
        {"hour": h, "label": _hour_label(h), "focus_seconds": hourly[h]}
        for h in sorted(range(24), key=lambda h: -hourly[h])[:3]
        if hourly[h] > 0
    ]
    bands = [
        {"name": name, "label": label, "focus_seconds": sum(hourly[h] for h in hours)}
        for name, label, hours in TIME_BANDS
    ]
    best_band = max(bands, key=lambda b: b["focus_seconds"])
    best_band = best_band if best_band["focus_seconds"] > 0 else None

    # ---------- 25분 이상 연속 집중 ----------
    deep = sorted(
        ((s, e) for s, e in segments if (e - s).total_seconds() >= DEEP_FOCUS_MIN_SEC),
        key=lambda x: x[0] - x[1],  # 긴 순
    )
    deep_focus = {
        "threshold_minutes": DEEP_FOCUS_MIN_SEC // 60,
        "count": len(deep),
        "total_seconds": int(sum((e - s).total_seconds() for s, e in deep)),
        "longest_seconds": int((deep[0][1] - deep[0][0]).total_seconds()) if deep else 0,
        "blocks": [
            {"start": s, "end": e, "minutes": int((e - s).total_seconds() // 60)}
            for s, e in deep[:10]
        ],
    }

    # ---------- 자리 이탈 / 휴대폰 ----------
    focus_hours = report["totals"]["total_seconds"] / 3600
    away_count, away_seconds, away_daily = _reason_stats(by_session, DistractionInterval.REASON_AWAY, range_start, range_end)
    phone_count, phone_seconds, phone_daily = _reason_stats(by_session, DistractionInterval.REASON_PHONE, range_start, range_end)
    away = {
        "count": away_count,
        "total_seconds": away_seconds,
        "per_hour": round(away_count / focus_hours, 2) if focus_hours > 0 else None,
    }
    phone = {
        "count": phone_count,
        "total_seconds": phone_seconds,
        "per_hour": round(phone_count / focus_hours, 2) if focus_hours > 0 else None,
    }
    for d in report["daily"]:
        d["away_count"] = away_daily.get(d["date"], 0)
        d["phone_count"] = phone_daily.get(d["date"], 0)

    # ---------- 이전 기간 대비 ----------
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    prev_focus = totals_by_user([user.id], prev_start, prev_end, now=now)[user.id]["focus_seconds"]
    cur_focus = report["totals"]["focus_seconds"]
    comparison = {
        "previous_start": prev_start.isoformat(),
        "previous_end": prev_end.isoformat(),
        "previous_focus_seconds": prev_focus,
        "change_rate": round(100 * (cur_focus - prev_focus) / prev_focus, 1) if prev_focus else None,
    }

    streak = _streaks(user, min(end, timezone.localdate(now)), goal_seconds, now)

    report.update({
        "hourly": [{"hour": h, "focus_seconds": hourly[h]} for h in range(24)],
        "best_hours": best_hours,
        "best_time_band": best_band,
        "deep_focus": deep_focus,
        "away": away,
        "phone": phone,
        "comparison": comparison,
        "streak": streak,
    })
    report["insights"] = _insights(report)
    return report


def _minutes(sec):
    m = sec // 60
    return f"{m // 60}시간 {m % 60}분" if m >= 60 else f"{m}분"


def _insights(r):
    """앱/웹에서 바로 보여줄 한 줄 요약들."""
    out = []
    t = r["totals"]
    if t["total_seconds"] == 0:
        return ["이 기간에는 공부 기록이 없어요. 책을 펴고 앉으면 자동으로 기록돼요!"]

    if r["best_hours"]:
        out.append(f"가장 집중이 잘 되는 시간은 {r['best_hours'][0]['label']}예요.")
    if r["best_time_band"]:
        out.append(f"{r['best_time_band']['label'].split(' ')[0]}에 가장 많이 공부했어요.")

    d = r["deep_focus"]
    if d["count"]:
        out.append(f"{d['threshold_minutes']}분 이상 연속 집중을 {d['count']}번 했어요. (최장 {_minutes(d['longest_seconds'])})")
    else:
        out.append(f"아직 {d['threshold_minutes']}분 이상 연속 집중한 구간이 없어요. 휴대폰을 멀리 두고 도전해 보세요!")

    if r["away"]["count"]:
        out.append(f"자리 이탈 {r['away']['count']}회 (공부 1시간당 {r['away']['per_hour']}회)")
    if r["phone"]["count"]:
        out.append(f"휴대폰 사용 {r['phone']['count']}회, 총 {_minutes(r['phone']['total_seconds'])}")

    g = r["goal"]
    out.append(f"하루 목표 {g['daily_goal_minutes']}분을 {g['days']}일 중 {g['achieved_days']}일 달성했어요.")

    c = r["comparison"]["change_rate"]
    if c is not None:
        out.append(f"이전 기간보다 순공부가 {abs(c)}% {'늘었어요 📈' if c >= 0 else '줄었어요 📉'}")
    if r["streak"]["current_days"] >= 2:
        out.append(f"{r['streak']['current_days']}일 연속 공부 중! 🔥")
    return out
