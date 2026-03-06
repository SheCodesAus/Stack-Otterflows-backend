from django.urls import path

from .views import (
    PodListCreateView, PodDetailView,
    PodMembershipListCreateView, PodMembershipAcceptView,
    PodGoalListCreateView,
    PodCheckInListCreateView, PodCheckInApproveView, PodCheckInRejectView, PodMembershipDeclineView, 
    ConnectionListCreateView, ConnectionAcceptView, ConnectionDeclineView,
)

urlpatterns = [

    # Pods
    path("pods/", PodListCreateView.as_view()),
    path("pods/<int:pod_id>/", PodDetailView.as_view()),
    path("pod-memberships/<int:membership_id>/decline/", PodMembershipDeclineView.as_view(), name="pod-membership-decline"),

    # Memberships
    path("pod-memberships/", PodMembershipListCreateView.as_view()),
    path("pod-memberships/<int:membership_id>/accept/", PodMembershipAcceptView.as_view()),

    # Goals
    path("pod-goals/", PodGoalListCreateView.as_view()),

    # Checkins
    path("pod-checkins/", PodCheckInListCreateView.as_view()),
    path("pod-checkins/<int:checkin_id>/approve/", PodCheckInApproveView.as_view()),
    path("pod-checkins/<int:checkin_id>/reject/", PodCheckInRejectView.as_view()),

    # Connections
    path("connections/", ConnectionListCreateView.as_view(), name="connection-list-create"),
    path("connections/<int:connection_id>/accept/", ConnectionAcceptView.as_view(), name="connection-accept"),
    path("connections/<int:connection_id>/decline/", ConnectionDeclineView.as_view(), name="connection-decline"),
]