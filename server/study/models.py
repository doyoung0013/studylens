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
    공부 세션 중 '딴짓'(휴대폰 사용 등)으로 판단된 구간.
    순공부 시간 = 세션 시간 - 딴짓 구간 시간
    """
    REASON_PHONE = "phone"
    REASON_CHOICES = [(REASON_PHONE, "휴대폰 사용")]

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
