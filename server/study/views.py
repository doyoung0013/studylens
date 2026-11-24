from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from rest_framework import parsers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DistractionInterval, StudyImage, StudySession
from .serializers import DistractionSerializer, StudyImageSerializer, StudySessionSerializer
from .services import (
    InvalidParam,
    daily_study_stats,
    local_day_bounds,
    parse_client_time,
    parse_date_param,
    process_uploaded_image,
    session_summary,
    signed_image_path,
    verify_image_signature,
)


def _bad_request(message):
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


def _open_session(user):
    return StudySession.objects.filter(user=user, end_time__isnull=True).order_by("-start_time").first()


def _close_session(session, end_time):
    """세션과 그 안의 진행 중 딴짓 구간을 end_time 으로 닫는다."""
    session.end_time = end_time
    session.save(update_fields=["end_time"])
    session.distractions.filter(end_time__isnull=True).update(end_time=end_time)
    # 세션 종료 이후로 늘어난 딴짓 구간은 잘라낸다
    session.distractions.filter(end_time__gt=end_time).update(end_time=end_time)


# ==================================================================
# Web (세션 로그인 기반 대시보드)
# ==================================================================
@require_http_methods(["GET", "POST"])
def login_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect("dashboard")
        return render(request, "login.html", {"error": "아이디 또는 비밀번호가 올바르지 않습니다."})

    return render(request, "login.html")


@require_http_methods(["GET", "POST"])
def signup_page(request):
    from django.contrib.auth.models import User

    from .social_views import SignupSerializer, signup_errors_to_message

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        serializer = SignupSerializer(data=request.POST)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("dashboard")
        return render(request, "signup.html", {
            "error": signup_errors_to_message(serializer.errors),
            "username": request.POST.get("username", ""),
        })

    return render(request, "signup.html")


@require_POST
def logout_page(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.localdate()

    week = daily_study_stats(user, today - timedelta(days=6), today)
    today_stat = week[-1]
    week_total = sum(d["total_seconds"] for d in week)
    week_focus = sum(d["focus_seconds"] for d in week)

    day_start, day_end = local_day_bounds(today)
    images = StudyImage.objects.filter(user=user, captured_at__gte=day_start, captured_at__lt=day_end)

    session = _open_session(user)
    current = session_summary(session) if session else None

    max_week = max([d["total_seconds"] for d in week] + [1])
    chart = [
        {
            "label": d["date"][5:].replace("-", "/"),
            "minutes": d["total_seconds"] // 60,
            "focus_minutes": d["focus_seconds"] // 60,
            "height": round(100 * d["total_seconds"] / max_week),
            # 막대 안에서 순공부가 차지하는 비율(%)
            "focus_pct": round(100 * d["focus_seconds"] / d["total_seconds"]) if d["total_seconds"] else 0,
        }
        for d in week
    ]

    context = {
        "today_minutes": today_stat["total_seconds"] // 60,
        "today_focus_minutes": today_stat["focus_seconds"] // 60,
        "today_distracted_minutes": today_stat["distracted_seconds"] // 60,
        "today_focus_rate": today_stat["focus_rate"],
        "week_hours": round(week_total / 3600, 1),
        "week_focus_hours": round(week_focus / 3600, 1),
        "image_count": images.count(),
        "image_urls": [signed_image_path(img) for img in images],
        "current": current,
        "current_minutes": current["elapsed_seconds"] // 60 if current else 0,
        "chart": chart,
    }
    return render(request, "dashboard.html", context)


# ==================================================================
# API — 공부 세션
# ==================================================================
class StudyStartView(APIView):
    """
    POST /api/study/start/   body(선택): {"start_time": ISO-8601}
    - 새 세션을 만든다.
    - 이전에 닫히지 않은 세션(Edge 비정상 종료 등)이 있으면 마지막 활동 시각으로 닫는다.
    """

    def post(self, request):
        try:
            start_time = parse_client_time(request.data.get("start_time"), "start_time")
        except InvalidParam as e:
            return _bad_request(str(e))

        with transaction.atomic():
            stale = _open_session(request.user)
            closed_stale = None
            if stale:
                end = min(max(stale.last_activity_time(), stale.start_time), start_time)
                _close_session(stale, max(end, stale.start_time))
                closed_stale = StudySessionSerializer(stale).data

            session = StudySession.objects.create(user=request.user, start_time=start_time)

        body = {"message": "공부 세션 시작", "session": StudySessionSerializer(session).data}
        if closed_stale:
            body["closed_stale_session"] = closed_stale
        return Response(body, status=status.HTTP_201_CREATED)


class StudyEndView(APIView):
    """
    POST /api/study/end/   body(선택): {"end_time": ISO-8601}
    - Edge는 '마지막으로 공부가 확인된 시각'을 end_time 으로 보낸다. (유예 시간은 공부 시간에서 제외)
    """

    def post(self, request):
        session = _open_session(request.user)
        if not session:
            return _bad_request("진행 중인 세션이 없습니다.")
        try:
            end_time = parse_client_time(
                request.data.get("end_time"), "end_time", not_before=session.start_time
            )
        except InvalidParam as e:
            return _bad_request(str(e))

        _close_session(session, end_time)
        return Response(
            {"message": "공부 세션 종료", "session": StudySessionSerializer(session).data},
            status=status.HTTP_200_OK,
        )


class CurrentStudyView(APIView):
    """
    GET /api/study/current/
    실시간 상태: 지금 공부 중인지, 몇 분째인지, 딴짓 중인지 + 오늘 누적 통계
    """

    def get(self, request):
        today = timezone.localdate()
        today_stat = daily_study_stats(request.user, today, today)[0]
        session = _open_session(request.user)
        return Response({
            "studying": session is not None,
            "session": session_summary(session) if session else None,
            "today": today_stat,
        })


# ==================================================================
# API — 딴짓(집중도)
# ==================================================================
class DistractionStartView(APIView):
    """
    POST /api/study/distraction/start/   body(선택): {"start_time": ISO-8601, "reason": "phone"}
    진행 중인 세션에 딴짓 구간을 연다. 이미 열려 있으면 그대로 반환.
    """

    def post(self, request):
        session = _open_session(request.user)
        if not session:
            return _bad_request("진행 중인 세션이 없습니다.")

        reason = request.data.get("reason") or DistractionInterval.REASON_PHONE
        if reason not in dict(DistractionInterval.REASON_CHOICES):
            return _bad_request("알 수 없는 reason 입니다.")

        try:
            start_time = parse_client_time(
                request.data.get("start_time"), "start_time", not_before=session.start_time
            )
        except InvalidParam as e:
            return _bad_request(str(e))

        existing = session.distractions.filter(end_time__isnull=True).first()
        if existing:
            return Response(DistractionSerializer(existing).data, status=status.HTTP_200_OK)

        interval = DistractionInterval.objects.create(session=session, reason=reason, start_time=start_time)
        return Response(DistractionSerializer(interval).data, status=status.HTTP_201_CREATED)


class DistractionEndView(APIView):
    """POST /api/study/distraction/end/   body(선택): {"end_time": ISO-8601}"""

    def post(self, request):
        interval = (
            DistractionInterval.objects
            .filter(session__user=request.user, end_time__isnull=True)
            .order_by("-start_time")
            .first()
        )
        if not interval:
            return _bad_request("진행 중인 딴짓 구간이 없습니다.")
        try:
            end_time = parse_client_time(
                request.data.get("end_time"), "end_time", not_before=interval.start_time
            )
        except InvalidParam as e:
            return _bad_request(str(e))

        interval.end_time = end_time
        interval.save(update_fields=["end_time"])
        return Response(DistractionSerializer(interval).data, status=status.HTTP_200_OK)


# ==================================================================
# API — 이미지
# ==================================================================
class ImageUploadView(APIView):
    """
    POST /api/image/upload/  (multipart/form-data)
    - image: 파일 (필수, JPEG/PNG/WEBP, 기본 최대 5MB)
    - session_id: 선택 (없으면 진행 중인 세션에 연결)
    - captured_at: 선택 (촬영 시각, 오프라인 큐 재전송용)
    """
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        user = request.user
        image_file = request.FILES.get("image")
        if not image_file:
            return _bad_request("image 파일이 필요합니다.")

        session_id = request.data.get("session_id")
        if session_id:
            try:
                session = StudySession.objects.get(id=int(session_id), user=user)
            except (ValueError, StudySession.DoesNotExist):
                return _bad_request("세션을 찾을 수 없습니다.")
        else:
            session = _open_session(user)

        try:
            captured_at = parse_client_time(request.data.get("captured_at"), "captured_at")
            content = process_uploaded_image(image_file)
        except InvalidParam as e:
            return _bad_request(str(e))

        study_image = StudyImage(user=user, session=session, captured_at=captured_at)
        study_image.image.save(content.name, content, save=True)

        serializer = StudyImageSerializer(study_image, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ImageFileView(APIView):
    """
    GET /api/images/<id>/file/?token=...
    서명된 토큰이 있어야만 이미지 파일을 내려준다. (/media/ 직접 공개 대신 사용)
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, image_id):
        token = request.query_params.get("token", "")
        if not verify_image_signature(image_id, token):
            raise Http404
        image = get_object_or_404(StudyImage, id=image_id)
        try:
            handle = image.image.open("rb")
        except FileNotFoundError:
            raise Http404
        response = FileResponse(handle, content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        return response


# ==================================================================
# API — 통계 & 갤러리
# ==================================================================
class DailyStatsView(APIView):
    """
    GET /api/stats/daily/?days=7               (오늘 기준 최근 N일, 1~366)
    GET /api/stats/daily/?start=YYYY-MM-DD&end=YYYY-MM-DD
    → [{"date", "total_seconds", "distracted_seconds", "focus_seconds", "focus_rate"}, ...]
    """

    def get(self, request):
        params = request.query_params
        try:
            if params.get("start") or params.get("end"):
                start = parse_date_param(params.get("start"), "start")
                end = parse_date_param(params.get("end"), "end")
            else:
                try:
                    days = int(params.get("days", 7))
                except ValueError:
                    raise InvalidParam("days는 정수여야 합니다.")
                if not 1 <= days <= 366:
                    raise InvalidParam("days는 1~366 사이여야 합니다.")
                end = timezone.localdate()
                start = end - timedelta(days=days - 1)
            result = daily_study_stats(request.user, start, end)
        except InvalidParam as e:
            return _bad_request(str(e))
        return Response(result, status=status.HTTP_200_OK)


class GalleryView(APIView):
    """
    GET /api/gallery/?date=YYYY-MM-DD   (date 생략 시 오늘)
    GET /api/gallery/today/             (하위 호환)
    """

    def get(self, request):
        raw = request.query_params.get("date")
        try:
            day = parse_date_param(raw, "date") if raw else timezone.localdate()
        except InvalidParam as e:
            return _bad_request(str(e))

        start, end = local_day_bounds(day)
        images = StudyImage.objects.filter(user=request.user, captured_at__gte=start, captured_at__lt=end)
        serializer = StudyImageSerializer(images, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
