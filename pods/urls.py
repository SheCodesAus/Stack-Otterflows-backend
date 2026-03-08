from django.urls import path

from .views import (
    PodListCreateView, PodDetailView,
    PodMembershipListCreateView, PodMembershipAcceptView,
    PodGoalListCreateView,
    PodCheckInListCreateView, PodCheckInApproveView, PodCheckInRejectView, PodMembershipDeclineView,
    ConnectionListCreateView, ConnectionAcceptView, ConnectionDeclineView,
    GoalListCreateView, GoalDetailView,
    GoalAssignmentListCreateView, GoalAssignmentAcceptView, GoalAssignmentDeclineView,
    CheckInListCreateView, CheckInApproveView, CheckInRejectView, CommentListCreateView, PodCommentListCreateView,
)

urlpatterns = [

     # Individual goals
    path("goals/", GoalListCreateView.as_view(), name="goal-list-create"),
    path("goals/<int:goal_id>/", GoalDetailView.as_view(), name="goal-detail"),

    # Goal assignments
    path("goal-assignments/", GoalAssignmentListCreateView.as_view(), name="goal-assignment-list-create"),
    path("goal-assignments/<int:assignment_id>/accept/", GoalAssignmentAcceptView.as_view(), name="goal-assignment-accept"),
    path("goal-assignments/<int:assignment_id>/decline/", GoalAssignmentDeclineView.as_view(), name="goal-assignment-decline"),

    # Individual check-ins
    path("checkins/", CheckInListCreateView.as_view(), name="checkin-list-create"),
    path("checkins/<int:checkin_id>/approve/", CheckInApproveView.as_view(), name="checkin-approve"),
    path("checkins/<int:checkin_id>/reject/", CheckInRejectView.as_view(), name="checkin-reject"),

    # Pods
    path("pods/", PodListCreateView.as_view()),
    path("pods/<int:pod_id>/", PodDetailView.as_view()),
    path("pod-memberships/<int:membership_id>/decline/", PodMembershipDeclineView.as_view(), name="pod-membership-decline"),

    # Memberships
    path("pod-memberships/", PodMembershipListCreateView.as_view()),
    path("pod-memberships/<int:membership_id>/accept/", PodMembershipAcceptView.as_view()),

    # Pod Goals
    path("pod-goals/", PodGoalListCreateView.as_view()),

    # Checkins
    path("pod-checkins/", PodCheckInListCreateView.as_view()),
    path("pod-checkins/<int:checkin_id>/approve/", PodCheckInApproveView.as_view()),
    path("pod-checkins/<int:checkin_id>/reject/", PodCheckInRejectView.as_view()),

    # Connections
    path("connections/", ConnectionListCreateView.as_view(), name="connection-list-create"),
    path("connections/<int:connection_id>/accept/", ConnectionAcceptView.as_view(), name="connection-accept"),
    path("connections/<int:connection_id>/decline/", ConnectionDeclineView.as_view(), name="connection-decline"),

    # Individual comments
    path("comments/", CommentListCreateView.as_view(), name="comment-list-create"),

    # Pod comments
    path("pod-comments/", PodCommentListCreateView.as_view(), name="pod-comment-list-create"),
]