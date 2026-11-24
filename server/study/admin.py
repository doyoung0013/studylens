from django.contrib import admin

from .models import (
    DistractionInterval,
    Friendship,
    GroupMembership,
    StudyGroup,
    StudyImage,
    StudySession,
    UserProfile,
)


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


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at", "accepted_at")
    list_filter = ("status",)


class MembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "invite_code", "created_at")
    search_fields = ("name", "invite_code")
    inlines = [MembershipInline]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "daily_goal_minutes")
