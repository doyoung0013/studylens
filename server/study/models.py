from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class StudySession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_sessions")
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.user.username} - {self.start_time} ~ {self.end_time}"

    @property
    def is_open(self):
        return self.end_time is None

    @property
    def duration_seconds(self):
        """
        확정된 세션의 실제 공부 시간(초). 진행 중인 세션이면 None.
        (이전 버전의 '최소 3분' 임시 보정은 제거됨)
        """
        if self.end_time is None:
            return None
        return max(0, int((self.end_time - self.start_time).total_seconds()))

    def last_activity_time(self):
        """세션에서 마지막으로 확인된 활동 시각 (마지막 이미지 촬영 시각 또는 시작 시각)."""
        last_image = self.images.order_by("-captured_at").values_list("captured_at", flat=True).first()
        if last_image and last_image > self.start_time:
            return last_image
        return self.start_time


class DistractionInterval(models.Model):
    """
    공부 세션 중 집중하지 못한 구간.
    - phone: 휴대폰 사용
    - away : 자리 이탈 (사람이 잠깐 안 보이거나, 상반신 위치가 크게 벗어남)
    순공부 시간 = 세션 시간 - (딴짓 구간들의 합집합)
    """
    REASON_PHONE = "phone"
    REASON_AWAY = "away"
    REASON_CHOICES = [(REASON_PHONE, "휴대폰 사용"), (REASON_AWAY, "자리 이탈")]

    session = models.ForeignKey(StudySession, on_delete=models.CASCADE, related_name="distractions")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_PHONE)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.session_id} {self.reason} {self.start_time} ~ {self.end_time}"


class StudyImage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_images")
    session = models.ForeignKey(
        StudySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="images",
    )
    image = models.ImageField(upload_to="study_images/%Y/%m/%d/")
    # 실제 촬영 시각 (오프라인 큐로 늦게 업로드돼도 촬영 날짜 기준으로 갤러리에 표시)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.user.username} - {self.captured_at}"


# ==================================================================
# 소셜 — 친구 & 스터디 그룹
# ==================================================================
class Friendship(models.Model):
    """
    친구 관계. from_user 가 요청을 보내고 to_user 가 수락하면 ACCEPTED.
    두 사용자 사이에는 방향과 관계없이 한 행만 존재한다.
    """
    PENDING = "pending"
    ACCEPTED = "accepted"
    STATUS_CHOICES = [(PENDING, "대기"), (ACCEPTED, "수락")]

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_requests_sent")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_requests_received")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="unique_friendship_pair"),
            models.CheckConstraint(condition=~models.Q(from_user=models.F("to_user")), name="no_self_friendship"),
        ]

    def __str__(self):
        return f"{self.from_user} → {self.to_user} ({self.status})"

    @classmethod
    def between(cls, a, b):
        return cls.objects.filter(
            models.Q(from_user=a, to_user=b) | models.Q(from_user=b, to_user=a)
        ).first()

    @classmethod
    def friend_ids(cls, user):
        rows = cls.objects.filter(
            models.Q(from_user=user) | models.Q(to_user=user), status=cls.ACCEPTED
        ).values_list("from_user_id", "to_user_id")
        return {b if a == user.id else a for a, b in rows}


class StudyGroup(models.Model):
    """초대 코드로 가입하는 스터디 그룹."""
    MAX_MEMBERS = 30

    name = models.CharField(max_length=30)
    description = models.CharField(max_length=200, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    invite_code = models.CharField(max_length=8, unique=True)
    members = models.ManyToManyField(User, through="GroupMembership", related_name="study_groups")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="unique_group_member"),
        ]

    def __str__(self):
        return f"{self.user} in {self.group}"


# ==================================================================
# 사용자 설정
# ==================================================================
class UserProfile(models.Model):
    """사용자별 설정. 지금은 하루 목표 순공부 시간만 가진다."""
    DEFAULT_GOAL_MINUTES = 60
    MIN_GOAL_MINUTES = 10
    MAX_GOAL_MINUTES = 16 * 60

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    daily_goal_minutes = models.PositiveIntegerField(default=DEFAULT_GOAL_MINUTES)

    def __str__(self):
        return f"{self.user.username} (목표 {self.daily_goal_minutes}분)"

    @classmethod
    def for_user(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile
