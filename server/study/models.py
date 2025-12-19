from django.db import models
from django.contrib.auth.models import User


class StudySession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.user.username} - {self.start_time} ~ {self.end_time}"

    @property
    def duration_seconds(self):
        """
        end_time까지 확정된 세션이면 duration을 초 단위로 계산.
        end_time이 없으면 None.
        """
        if self.end_time is None:
            return None

        seconds = int((self.end_time - self.start_time).total_seconds())

        # 임시 보정 (최소 3분)
        return max(seconds, 180)


class StudyImage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_images')
    session = models.ForeignKey(
        StudySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='images'
    )
    image = models.ImageField(upload_to='study_images/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.created_at}"
