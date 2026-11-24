"""
회원가입 / 내 정보 / 친구 / 스터디 그룹 API.
"""
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Friendship, GroupMembership, StudyGroup
from .services import InvalidParam, build_ranking, generate_invite_code

MAX_GROUPS_PER_USER = 20


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
    """GET /api/me/  내 정보 + 친구/그룹 수 + 받은 친구 요청 수"""

    def get(self, request):
        user = request.user
        return Response({
            **_user_brief(user),
            "date_joined": user.date_joined,
            "friend_count": len(Friendship.friend_ids(user)),
            "pending_friend_requests": Friendship.objects.filter(to_user=user, status=Friendship.PENDING).count(),
            "group_count": user.group_memberships.count(),
        })


# ==================================================================
# 친구
# ==================================================================
def _period(request):
    period = request.query_params.get("period", "week")
    return period


class FriendListView(APIView):
    """GET /api/friends/  친구 목록"""

    def get(self, request):
        ids = Friendship.friend_ids(request.user)
        friends = User.objects.filter(id__in=ids).order_by("username")
        return Response([_user_brief(u) for u in friends])


class FriendDeleteView(APIView):
    """DELETE /api/friends/<user_id>/  친구 삭제"""

    def delete(self, request, user_id):
        other = get_object_or_404(User, id=user_id)
        relation = Friendship.between(request.user, other)
        if not relation or relation.status != Friendship.ACCEPTED:
            return Response({"detail": "친구가 아닙니다."}, status=status.HTTP_404_NOT_FOUND)
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendRequestView(APIView):
    """
    GET  /api/friends/requests/   받은/보낸 대기 중 요청
    POST /api/friends/requests/   {username}  친구 요청 보내기
         - 상대가 이미 나에게 요청했다면 바로 친구가 된다.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "friend_request"

    def get_throttles(self):
        # 조회(GET)는 제한하지 않고 요청 보내기(POST)만 제한
        return super().get_throttles() if self.request.method == "POST" else []

    def get(self, request):
        user = request.user
        received = Friendship.objects.filter(to_user=user, status=Friendship.PENDING).select_related("from_user")
        sent = Friendship.objects.filter(from_user=user, status=Friendship.PENDING).select_related("to_user")
        return Response({
            "received": [{"id": r.id, "user": _user_brief(r.from_user), "created_at": r.created_at} for r in received],
            "sent": [{"id": r.id, "user": _user_brief(r.to_user), "created_at": r.created_at} for r in sent],
        })

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        if not username:
            return _bad_request("username이 필요합니다.")
        other = User.objects.filter(username__iexact=username, is_active=True).first()
        if other is None:
            return Response({"detail": "해당 아이디의 사용자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if other == request.user:
            return _bad_request("자기 자신에게는 친구 요청을 보낼 수 없습니다.")

        with transaction.atomic():
            relation = Friendship.between(request.user, other)
            if relation and relation.status == Friendship.ACCEPTED:
                return _bad_request("이미 친구입니다.")
            if relation and relation.from_user_id == request.user.id:
                return Response({"detail": "이미 친구 요청을 보냈습니다.", "status": "pending"})
            if relation:  # 상대가 먼저 보낸 요청이 있음 → 수락 처리
                relation.status = Friendship.ACCEPTED
                relation.accepted_at = timezone.now()
                relation.save(update_fields=["status", "accepted_at"])
                return Response({"detail": f"{other.username}님과 친구가 되었습니다.", "status": "accepted"})

            Friendship.objects.create(from_user=request.user, to_user=other)
        return Response(
            {"detail": f"{other.username}님에게 친구 요청을 보냈습니다.", "status": "pending"},
            status=status.HTTP_201_CREATED,
        )


class FriendRequestActionView(APIView):
    """
    POST /api/friends/requests/<id>/accept/   받은 요청 수락
    POST /api/friends/requests/<id>/reject/   받은 요청 거절
    POST /api/friends/requests/<id>/cancel/   보낸 요청 취소
    """

    def post(self, request, request_id, action):
        relation = get_object_or_404(Friendship, id=request_id, status=Friendship.PENDING)
        user = request.user

        if action in ("accept", "reject") and relation.to_user_id != user.id:
            return Response({"detail": "요청을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if action == "cancel" and relation.from_user_id != user.id:
            return Response({"detail": "요청을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        if action == "accept":
            relation.status = Friendship.ACCEPTED
            relation.accepted_at = timezone.now()
            relation.save(update_fields=["status", "accepted_at"])
            return Response({"detail": "친구 요청을 수락했습니다.", "status": "accepted"})

        relation.delete()
        return Response({"detail": "처리되었습니다."})


class FriendRankingView(APIView):
    """GET /api/friends/ranking/?period=today|week|month   나 + 친구 순공부 랭킹"""

    def get(self, request):
        ids = Friendship.friend_ids(request.user) | {request.user.id}
        try:
            data = build_ranking(User.objects.filter(id__in=ids), request.user, _period(request))
        except InvalidParam as e:
            return _bad_request(str(e))
        return Response(data)


# ==================================================================
# 스터디 그룹
# ==================================================================
class GroupSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = ["id", "name", "description", "owner", "is_owner", "member_count", "invite_code", "created_at"]
        read_only_fields = ["invite_code", "created_at"]

    def get_owner(self, obj):
        return _user_brief(obj.owner)

    def get_member_count(self, obj):
        return getattr(obj, "num_members", None) or obj.memberships.count()

    def get_is_owner(self, obj):
        return obj.owner_id == self.context["request"].user.id

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("그룹 이름을 입력해 주세요.")
        return value


def _my_group(request, group_id):
    return get_object_or_404(StudyGroup, id=group_id, memberships__user=request.user)


class GroupListCreateView(APIView):
    """
    GET  /api/groups/   내가 속한 그룹 목록
    POST /api/groups/   {name, description?}  그룹 만들기 (만든 사람이 방장)
    """

    def get(self, request):
        groups = (
            StudyGroup.objects.filter(memberships__user=request.user)
            .select_related("owner")
            .annotate(num_members=Count("memberships", distinct=True))
        )
        return Response(GroupSerializer(groups, many=True, context={"request": request}).data)

    def post(self, request):
        if request.user.group_memberships.count() >= MAX_GROUPS_PER_USER:
            return _bad_request(f"그룹은 최대 {MAX_GROUPS_PER_USER}개까지 참여할 수 있습니다.")
        serializer = GroupSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            first = next(iter(serializer.errors.values()))
            return _bad_request(str(first[0] if isinstance(first, list) else first))

        with transaction.atomic():
            group = serializer.save(owner=request.user, invite_code=generate_invite_code())
            GroupMembership.objects.create(group=group, user=request.user)
        return Response(GroupSerializer(group, context={"request": request}).data, status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    """
    GET    /api/groups/<id>/   그룹 정보 + 멤버 목록 (멤버만)
    DELETE /api/groups/<id>/   그룹 삭제 (방장만)
    """

    def get(self, request, group_id):
        group = _my_group(request, group_id)
        data = GroupSerializer(group, context={"request": request}).data
        data["members"] = [
            {**_user_brief(m.user), "joined_at": m.joined_at, "is_owner": m.user_id == group.owner_id}
            for m in group.memberships.select_related("user")
        ]
        return Response(data)

    def delete(self, request, group_id):
        group = _my_group(request, group_id)
        if group.owner_id != request.user.id:
            return Response({"detail": "방장만 그룹을 삭제할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupJoinView(APIView):
    """POST /api/groups/join/   {invite_code}"""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "group_join"

    def post(self, request):
        code = (request.data.get("invite_code") or "").strip().upper()
        group = StudyGroup.objects.filter(invite_code=code).first() if code else None
        if group is None:
            return Response({"detail": "초대 코드가 올바르지 않습니다."}, status=status.HTTP_404_NOT_FOUND)
        if group.memberships.filter(user=request.user).exists():
            return Response(GroupSerializer(group, context={"request": request}).data)
        if group.memberships.count() >= StudyGroup.MAX_MEMBERS:
            return _bad_request(f"그룹 인원이 가득 찼습니다. (최대 {StudyGroup.MAX_MEMBERS}명)")
        if request.user.group_memberships.count() >= MAX_GROUPS_PER_USER:
            return _bad_request(f"그룹은 최대 {MAX_GROUPS_PER_USER}개까지 참여할 수 있습니다.")

        GroupMembership.objects.get_or_create(group=group, user=request.user)
        return Response(GroupSerializer(group, context={"request": request}).data, status=status.HTTP_201_CREATED)


class GroupLeaveView(APIView):
    """
    POST /api/groups/<id>/leave/
    방장이 나가면 가장 먼저 가입한 멤버에게 방장이 넘어가고, 마지막 멤버가 나가면 그룹이 삭제된다.
    """

    def post(self, request, group_id):
        group = _my_group(request, group_id)
        with transaction.atomic():
            group.memberships.filter(user=request.user).delete()
            remaining = group.memberships.order_by("joined_at").first()
            if remaining is None:
                group.delete()
                return Response({"detail": "그룹을 나갔습니다. (마지막 멤버라 그룹이 삭제되었습니다)"})
            if group.owner_id == request.user.id:
                group.owner_id = remaining.user_id
                group.save(update_fields=["owner"])
        return Response({"detail": "그룹을 나갔습니다."})


class GroupInviteCodeView(APIView):
    """POST /api/groups/<id>/invite-code/   초대 코드 재발급 (방장만, 기존 코드는 무효)"""

    def post(self, request, group_id):
        group = _my_group(request, group_id)
        if group.owner_id != request.user.id:
            return Response({"detail": "방장만 초대 코드를 바꿀 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        group.invite_code = generate_invite_code()
        group.save(update_fields=["invite_code"])
        return Response({"invite_code": group.invite_code})


class GroupRankingView(APIView):
    """GET /api/groups/<id>/ranking/?period=today|week|month   그룹 멤버 순공부 랭킹"""

    def get(self, request, group_id):
        group = _my_group(request, group_id)
        members = User.objects.filter(group_memberships__group=group)
        try:
            data = build_ranking(members, request.user, _period(request))
        except InvalidParam as e:
            return _bad_request(str(e))
        data["group"] = {"id": group.id, "name": group.name}
        return Response(data)
