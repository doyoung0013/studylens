from django.contrib import admin

from .models import DistractionInterval, StudyImage, StudySession


class DistractionInline(admin.TabularInline):
    model = DistractionInterval
    extra = 0


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ("user", "start_time", "end_time", "duration_seconds")
    list_filter = ("user",)
    inlines = [DistractionInline]


@admin.register(StudyImage)
class StudyImageAdmin(admin.ModelAdmin):
    list_display = ("user", "session", "captured_at", "created_at")
    list_filter = ("user",)
