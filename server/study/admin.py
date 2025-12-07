# study/admin.py
from django.contrib import admin
from .models import StudySession, StudyImage


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_time', 'end_time', 'duration_seconds')
    list_filter = ('user',)


@admin.register(StudyImage)
class StudyImageAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'created_at')
    list_filter = ('user', 'session')
