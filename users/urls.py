from django.urls import path
from .views import RegisterView, MeView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("me/", MeView.as_view(), name="me"),
]