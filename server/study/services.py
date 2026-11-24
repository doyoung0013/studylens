"""
StudyLens 도메인 로직 (뷰와 분리해서 테스트하기 쉽게 유지).

- 날짜별 공부/딴짓/순공부 시간 집계 (자정을 넘긴 구간은 날짜 경계에서 분할)
- 진행 중 세션 요약 (실시간 상태)
- 클라이언트가 보낸 시각 검증/보정
- 업로드 이미지 검증 및 재인코딩 (리사이즈 + EXIF 제거)
- 서명된 이미지 URL
"""
from datetime import datetime, time, timedelta
from io import BytesIO

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import DistractionInterval, StudySession

MAX_RANGE_DAYS = 366


# ------------------------------------------------------------------
# 날짜/시각 파싱
# ------------------------------------------------------------------
class InvalidParam(ValueError):
    pass


def parse_date_param(value, name="date"):
    """'YYYY-MM-DD' 문자열 → date. 형식이 잘못되면 InvalidParam."""
    try:
        parsed = parse_date(value) if value else None
    except ValueError:
        parsed = None
    if parsed is None:
        raise InvalidParam(f"{name}는 YYYY-MM-DD 형식이어야 합니다.")
    return parsed


def parse_client_time(value, name, *, not_before=None, now=None):
    """
    Edge가 보낸 ISO-8601 시각을 검증해서 반환한다. 값이 없으면 now.
    - 미래 시각 → now 로 보정
    - not_before 보다 이전 → not_before 로 보정
    - 너무 오래된 과거(STUDYLENS_MAX_BACKDATE_SEC 초과) → InvalidParam
    """
    now = now or timezone.now()
    if not value:
        result = now
    else:
        try:
            result = parse_datetime(str(value))
        except ValueError:
            result = None
        if result is None:
            raise InvalidParam(f"{name}는 ISO-8601 형식이어야 합니다.")
        if timezone.is_naive(result):
            result = timezone.make_aware(result, timezone.get_current_timezone())
        if now - result > timedelta(seconds=settings.STUDYLENS_MAX_BACKDATE_SEC):
            raise InvalidParam(f"{name}가 너무 오래된 시각입니다.")
        result = min(result, now)
    if not_before is not None:
        result = max(result, not_before)
    return result


def local_day_bounds(day):
    """로컬 날짜 하루의 [시작, 끝) aware datetime."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), tz)
    return start, end


# ------------------------------------------------------------------
# 공부 시간 집계
# ------------------------------------------------------------------
def _overlapping(queryset, range_start, range_end):
    """[range_start, range_end) 와 겹치는 구간의 (start, end) 목록 — 한 번의 쿼리, 필요한 컬럼만."""
    return (
        queryset
        .filter(start_time__lt=range_end)
        .exclude(end_time__isnull=False, end_time__lte=range_start)
        .values_list("start_time", "end_time")
    )


def _accumulate_by_day(intervals, totals, range_start, range_end, now):
    """구간들을 로컬 날짜 경계에서 잘라 totals[date] 에 초 단위로 더한다. 진행 중(end=None)은 now까지."""
    tz = timezone.get_current_timezone()
    for s_time, e_time in intervals:
        seg_start = max(s_time, range_start)
        seg_end = min(e_time or now, range_end, now)
        while seg_start < seg_end:
            day = timezone.localtime(seg_start, tz).date()
            _, day_end = local_day_bounds(day)
            piece_end = min(seg_end, day_end)
            if day in totals:
                totals[day] += (piece_end - seg_start).total_seconds()
            seg_start = piece_end


def focus_rate(total_seconds, distracted_seconds):
    """집중도(%) = 순공부 / 전체. 공부 기록이 없으면 None."""
    if total_seconds <= 0:
        return None
    return round(100 * (total_seconds - distracted_seconds) / total_seconds, 1)


def daily_study_stats(user, start_date, end_date, now=None):
    """
    [start_date, end_date] (로컬 날짜, 양끝 포함) 범위의 날짜별 공부 통계.
    - 자정을 넘긴 세션/딴짓 구간은 날짜별로 나눠서 합산
    - 진행 중인 세션/딴짓은 현재 시각까지 포함
    반환 (날짜 오름차순, 기록 없는 날도 0으로 포함):
      [{"date", "total_seconds", "distracted_seconds", "focus_seconds", "focus_rate"}, ...]
    """
    if end_date < start_date:
        raise InvalidParam("end는 start보다 같거나 이후여야 합니다.")
    days = (end_date - start_date).days + 1
    if days > MAX_RANGE_DAYS:
        raise InvalidParam(f"조회 기간은 최대 {MAX_RANGE_DAYS}일입니다.")

    now = now or timezone.now()
    range_start, _ = local_day_bounds(start_date)
    _, range_end = local_day_bounds(end_date)

    all_days = [start_date + timedelta(days=i) for i in range(days)]
    study = dict.fromkeys(all_days, 0.0)
    distracted = dict.fromkeys(all_days, 0.0)

    _accumulate_by_day(
        _overlapping(StudySession.objects.filter(user=user), range_start, range_end),
        study, range_start, range_end, now,
    )
    _accumulate_by_day(
        _overlapping(DistractionInterval.objects.filter(session__user=user), range_start, range_end),
        distracted, range_start, range_end, now,
    )

    result = []
    for day in all_days:
        total = int(study[day])
        dist = min(int(distracted[day]), total)
        result.append({
            "date": day.isoformat(),
            "total_seconds": total,
            "distracted_seconds": dist,
            "focus_seconds": total - dist,
            "focus_rate": focus_rate(total, dist),
        })
    return result


def session_summary(session, now=None):
    """진행 중/완료된 세션 하나의 경과·딴짓·순공부 시간."""
    now = now or timezone.now()
    end = session.end_time or now
    elapsed = max(0, int((end - session.start_time).total_seconds()))

    distracted = 0.0
    open_distraction = None
    for d in session.distractions.all():
        d_end = min(d.end_time or now, end)
        d_start = max(d.start_time, session.start_time)
        if d_end > d_start:
            distracted += (d_end - d_start).total_seconds()
        if d.end_time is None:
            open_distraction = d

    distracted = min(int(distracted), elapsed)
    return {
        "id": session.id,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "elapsed_seconds": elapsed,
        "distracted_seconds": distracted,
        "focus_seconds": elapsed - distracted,
        "focus_rate": focus_rate(elapsed, distracted),
        "is_distracted": open_distraction is not None,
        "distracted_since": open_distraction.start_time if open_distraction else None,
    }


# ------------------------------------------------------------------
# 업로드 이미지 처리
# ------------------------------------------------------------------
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def process_uploaded_image(uploaded_file):
    """
    업로드 파일을 검증하고 JPEG로 재인코딩한 ContentFile 을 반환한다.
    - 크기 제한, 실제 이미지 여부/포맷 검사
    - 긴 변을 STUDYLENS_MAX_IMAGE_SIDE 로 축소
    - 재인코딩으로 EXIF(위치정보 등) 메타데이터 제거
    """
    if uploaded_file.size > settings.STUDYLENS_MAX_IMAGE_BYTES:
        limit_mb = settings.STUDYLENS_MAX_IMAGE_BYTES / (1024 * 1024)
        raise InvalidParam(f"이미지는 최대 {limit_mb:.0f}MB까지 업로드할 수 있습니다.")

    try:
        uploaded_file.seek(0)
        probe = Image.open(uploaded_file)
        fmt = probe.format
        probe.verify()
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise InvalidParam("올바른 이미지 파일이 아닙니다.")

    if fmt not in ALLOWED_FORMATS:
        raise InvalidParam("JPEG, PNG, WEBP 이미지만 업로드할 수 있습니다.")

    img = ImageOps.exif_transpose(img).convert("RGB")
    side = settings.STUDYLENS_MAX_IMAGE_SIDE
    img.thumbnail((side, side))

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)
    return ContentFile(buffer.getvalue(), name="study.jpg")


# ------------------------------------------------------------------
# 서명된 이미지 URL
# ------------------------------------------------------------------
_IMAGE_SALT = "studylens.image"


def sign_image(image_id):
    return signing.TimestampSigner(salt=_IMAGE_SALT).sign(str(image_id))


def verify_image_signature(image_id, token):
    try:
        value = signing.TimestampSigner(salt=_IMAGE_SALT).unsign(
            token, max_age=settings.STUDYLENS_IMAGE_URL_MAX_AGE
        )
    except signing.BadSignature:
        return False
    return value == str(image_id)


def signed_image_path(image):
    return f"{reverse('image_file', args=[image.id])}?token={sign_image(image.id)}"
