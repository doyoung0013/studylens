from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import login_page, dashboard_view

from .views import (
    StudyStartView,
    StudyEndView,
    ImageUploadView,
    DailyStatsView,
    TodayGalleryView,
)

urlpatterns = [
    # Auth (JWT)
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Study session
    path('study/start/', StudyStartView.as_view(), name='study_start'),
    path('study/end/', StudyEndView.as_view(), name='study_end'),

    # Image
    path('image/upload/', ImageUploadView.as_view(), name='image_upload'),

    # Stats & Gallery
    path('stats/daily/', DailyStatsView.as_view(), name='stats_daily'),
    path('gallery/today/', TodayGalleryView.as_view(), name='today_gallery'),

    path("", login_page),      
    path("dashboard/", dashboard_view, name="dashboard"),
]
