from rest_framework import serializers

from .models import DistractionInterval, StudyImage, StudySession
from .services import signed_image_path


class StudySessionSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = StudySession
        fields = ["id", "start_time", "end_time", "duration_seconds"]


class DistractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistractionInterval
        fields = ["id", "session", "reason", "start_time", "end_time"]


class StudyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = StudyImage
        fields = ["id", "session", "image_url", "captured_at", "created_at"]

    def get_image_url(self, obj):
        """일정 시간만 유효한 서명된 URL (Glide 등에서 헤더 없이 바로 로드 가능)."""
        path = signed_image_path(obj)
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path
