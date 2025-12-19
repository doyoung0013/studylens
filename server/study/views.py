from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, parsers

from .models import StudySession, StudyImage
from .serializers import StudySessionSerializer, StudyImageSerializer
from rest_framework.permissions import IsAuthenticated

from django.contrib.auth.decorators import login_required
from .models import StudySession

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

def login_page(request):
    if request.method == "GET":
        return render(request, "login.html")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("/dashboard/")
        else:
            return render(request, "login.html", {"error": "로그인 실패"})

@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.localdate()

    # -----------------------------
    # 1. 오늘 공부 시간 (초 → 분)
    # -----------------------------
    today_sessions = StudySession.objects.filter(
        user=user,
        start_time__date=today,
        end_time__isnull=False
    )

    today_seconds = sum(
        [s.duration_seconds or 0 for s in today_sessions]
    )
    today_minutes = today_seconds // 60

    # -----------------------------
    # 2. 최근 7일 총 공부 시간 (초 → 시간)
    # -----------------------------
    start_date = today - timedelta(days=6)

    week_sessions = StudySession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=today,
        end_time__isnull=False
    )

    week_seconds = sum(
        [s.duration_seconds or 0 for s in week_sessions]
    )
    week_hours = round(week_seconds / 3600, 1)

    # -----------------------------
    # 3. 오늘 촬영된 이미지
    # -----------------------------
    today_images = StudyImage.objects.filter(
        user=user,
        created_at__date=today
    )

    image_count = today_images.count()

    context = {
        "today_minutes": today_minutes,
        "week_hours": week_hours,
        "image_count": image_count,
        "images": today_images,
    }

    return render(request, "dashboard.html", context)

class StudyStartView(APIView):
    """
    POST /study/start/
    - 현재 열려있는 세션이 있다면 그대로 반환
    - 없으면 새로운 세션 생성
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        open_session = StudySession.objects.filter(user=user, end_time__isnull=True).first()
        if open_session:
            serializer = StudySessionSerializer(open_session)
            return Response({'message': '이미 진행 중인 세션이 있습니다.', 'session': serializer.data},
                            status=status.HTTP_200_OK)

        now = timezone.now()
        session = StudySession.objects.create(user=user, start_time=now)

        serializer = StudySessionSerializer(session)
        return Response({'message': '공부 세션 시작', 'session': serializer.data},
                        status=status.HTTP_201_CREATED)


class StudyEndView(APIView):
    """
    POST /study/end/
    - 현재 열려있는 세션의 end_time을 now로 설정
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        open_session = StudySession.objects.filter(user=user, end_time__isnull=True).first()
        if not open_session:
            return Response({'message': '진행 중인 세션이 없습니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        open_session.end_time = timezone.now()
        open_session.save()

        serializer = StudySessionSerializer(open_session)
        return Response({'message': '공부 세션 종료', 'session': serializer.data},
                        status=status.HTTP_200_OK)


class ImageUploadView(APIView):
    """
    POST /image/upload/
    - multipart/form-data로 이미지 업로드
    - 필드:
    - image: 파일 (필수)
    - session_id: 선택 (연결하고 싶으면)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        user = request.user
        image_file = request.FILES.get('image')
        session_id = request.data.get('session_id')

        if not image_file:
            return Response({'detail': 'image 파일이 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        session = None
        if session_id:
            try:
                session = StudySession.objects.get(id=session_id, user=user)
            except StudySession.DoesNotExist:
                return Response({'detail': '세션을 찾을 수 없습니다.'},
                                status=status.HTTP_400_BAD_REQUEST)

        study_image = StudyImage.objects.create(
            user=user,
            session=session,
            image=image_file
        )

        serializer = StudyImageSerializer(study_image, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DailyStatsView(APIView):
    """
    GET /stats/daily/?days=7
    - 최근 N일 동안 날짜별 공부 총 시간(초) 리턴
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        days = int(request.query_params.get('days', 7))

        end_date = timezone.localdate()          # 오늘 날짜 (로컬)
        start_date = end_date - timedelta(days=days - 1)

        # end_time이 있는 세션만 duration 계산
        sessions = StudySession.objects.filter(
            user=user,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
            end_time__isnull=False,
        )

        # 날짜별로 수동 집계
        result = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_sessions = [s for s in sessions if s.start_time.date() == day]
            total_seconds = sum([s.duration_seconds or 0 for s in day_sessions])

            result.append({
                'date': str(day),
                'total_seconds': total_seconds,
            })

        return Response(result, status=status.HTTP_200_OK)


class TodayGalleryView(APIView):
    """
    GET /gallery/today/
    - 오늘 찍힌 공부 이미지 리스트
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.localdate()

        images = StudyImage.objects.filter(
            user=user,
            created_at__date=today,
        )

        serializer = StudyImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
