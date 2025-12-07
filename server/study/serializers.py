from rest_framework import serializers
from django.contrib.auth.models import User
from .models import StudySession, StudyImage


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class StudySessionSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = StudySession
        fields = ['id', 'start_time', 'end_time', 'duration_seconds']

    def get_duration_seconds(self, obj):
        return obj.duration_seconds


class StudyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = StudyImage
        fields = ['id', 'session', 'image_url', 'created_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)
