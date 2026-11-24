from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import social_views as social
from . import views

urlpatterns = [
    # Auth (JWT)
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/signup/", social.SignupView.as_view(), name="signup"),
    path("me/", social.MeView.as_view(), name="me"),

    # Study session
    path("study/start/", views.StudyStartView.as_view(), name="study_start"),
    path("study/end/", views.StudyEndView.as_view(), name="study_end"),
    path("study/current/", views.CurrentStudyView.as_view(), name="study_current"),

    # Distraction (집중도)
    path("study/distraction/start/", views.DistractionStartView.as_view(), name="distraction_start"),
    path("study/distraction/end/", views.DistractionEndView.as_view(), name="distraction_end"),

    # Image
    path("image/upload/", views.ImageUploadView.as_view(), name="image_upload"),
    path("images/<int:image_id>/file/", views.ImageFileView.as_view(), name="image_file"),

    # Stats & Gallery
    path("stats/daily/", views.DailyStatsView.as_view(), name="stats_daily"),
    path("gallery/", views.GalleryView.as_view(), name="gallery"),
    path("gallery/today/", views.GalleryView.as_view(), name="today_gallery"),

    # Friends
    path("friends/", social.FriendListView.as_view(), name="friends"),
    path("friends/<int:user_id>/", social.FriendDeleteView.as_view(), name="friend_delete"),
    path("friends/requests/", social.FriendRequestView.as_view(), name="friend_requests"),
    path(
        "friends/requests/<int:request_id>/<str:action>/",
        social.FriendRequestActionView.as_view(),
        name="friend_request_action",
    ),
    path("friends/ranking/", social.FriendRankingView.as_view(), name="friend_ranking"),

    # Study groups
    path("groups/", social.GroupListCreateView.as_view(), name="groups"),
    path("groups/join/", social.GroupJoinView.as_view(), name="group_join"),
    path("groups/<int:group_id>/", social.GroupDetailView.as_view(), name="group_detail"),
    path("groups/<int:group_id>/leave/", social.GroupLeaveView.as_view(), name="group_leave"),
    path("groups/<int:group_id>/invite-code/", social.GroupInviteCodeView.as_view(), name="group_invite_code"),
    path("groups/<int:group_id>/ranking/", social.GroupRankingView.as_view(), name="group_ranking"),
]
