from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    PodListCreateView, PodDetailView,
    PodMembershipListCreateView, PodMembershipAcceptView,
    PodGoalListCreateView,
    PodCheckInListCreateView, PodCheckInApproveView, PodCheckInRejectView,
)

urlpatterns = [
    # Auth
    path("api/auth/token/", obtain_auth_token),
    path("api/", include("pods.urls")),

    # Pods
    path("pods/", PodListCreateView.as_view()),
    path("pods/<int:pod_id>/", PodDetailView.as_view()),

    # Memberships
    path("pod-memberships/", PodMembershipListCreateView.as_view()),
    path("pod-memberships/<int:membership_id>/accept/", PodMembershipAcceptView.as_view()),

    # Goals
    path("pod-goals/", PodGoalListCreateView.as_view()),

    # Checkins
    path("pod-checkins/", PodCheckInListCreateView.as_view()),
    path("pod-checkins/<int:checkin_id>/approve/", PodCheckInApproveView.as_view()),
    path("pod-checkins/<int:checkin_id>/reject/", PodCheckInRejectView.as_view()),
]