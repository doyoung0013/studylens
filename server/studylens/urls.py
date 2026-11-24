# studylens/urls.py
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("study.api_urls")),   # REST API (Edge / Android)
    path("", include("study.web_urls")),       # 웹 대시보드
]
# 업로드 이미지는 /media/ 로 공개하지 않고 서명된 URL(/api/images/<id>/file/)로만 제공한다.
