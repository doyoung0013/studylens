from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
    path("logout/", views.logout_page, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]
