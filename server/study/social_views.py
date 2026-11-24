"""
회원가입 / 내 정보 API.
"""
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


def _bad_request(message):
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


def _user_brief(user):
    return {"id": user.id, "username": user.username}


# ==================================================================
# 회원가입 / 내 정보
# ==================================================================
class SignupSerializer(serializers.Serializer):
    username = serializers.RegexField(
        r"^[A-Za-z0-9_.]{4,20}$",
        error_messages={"invalid": "아이디는 영문, 숫자, _ . 조합 4~20자여야 합니다."},
    )
    password = serializers.CharField(write_only=True, max_length=128)
    password2 = serializers.CharField(write_only=True, max_length=128)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "비밀번호가 일치하지 않습니다."})
        try:
            validate_password(attrs["password"], user=User(username=attrs["username"]))
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated):
        return User.objects.create_user(username=validated["username"], password=validated["password"])


def signup_errors_to_message(errors):
    """DRF 에러 dict → 앱에서 바로 보여줄 한 줄 메시지."""
    for key in ("username", "password", "password2", "non_field_errors"):
        if key in errors:
            value = errors[key]
            return str(value[0] if isinstance(value, list) else value)
    return "입력값을 확인해 주세요."


class SignupView(APIView):
    """
    POST /api/auth/signup/   {username, password, password2}
    가입 후 바로 로그인된 상태가 되도록 JWT를 함께 반환한다.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": signup_errors_to_message(serializer.errors), "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = serializer.save()
        except IntegrityError:
            return _bad_request("이미 사용 중인 아이디입니다.")

        refresh = RefreshToken.for_user(user)
        return Response(
            {"user": _user_brief(user), "access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    """GET /api/me/  내 정보"""

    def get(self, request):
        user = request.user
        return Response({**_user_brief(user), "date_joined": user.date_joined})
