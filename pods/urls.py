from django.urls import path

from .views import (
    GoalListCreateView,
    GoalDetailView,
    GoalAssignmentListCreateView,
    GoalAssignmentAcceptView,
    GoalAssignmentDeclineView,
    CheckInListCreateView,
    CheckInDetailView,
    CheckInApproveView,
    CheckInRejectView,
    CommentListCreateView,
    CommentDetailView,
    PodListCreateView,
    PodDetailView,
    PodMembershipListCreateView,
    PodMembershipAcceptView,
    PodMembershipDeclineView,
    PodGoalListCreateView,
    PodGoalDetailView,
    PodCheckInListCreateView,
    PodCheckInDetailView,
    PodCheckInApproveView,
    PodCheckInRejectView,
    PodCommentListCreateView,
    PodCommentDetailView,
    ConnectionListCreateView,
    ConnectionAcceptView,
    ConnectionDeclineView,
    NotificationListView,
    NotificationSummaryView,
    NotificationMarkReadView,
    NotificationMarkUnreadView,
    NotificationResolveView,
    NotificationMarkAllReadView,
    UserSearchView,
    PodInviteCandidateView,
    PodMembershipRoleUpdateView,
    PodMembershipRemoveView,
    PodMembershipCancelView,
    PodMembershipResendView,
    ConnectionQrInviteCreateView,
    ConnectionQrInviteClaimView,
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
    path("checkins/<int:checkin_id>/", CheckInDetailView.as_view(), name="checkin-detail"),
    path("checkins/<int:checkin_id>/approve/", CheckInApproveView.as_view(), name="checkin-approve"),
    path("checkins/<int:checkin_id>/reject/", CheckInRejectView.as_view(), name="checkin-reject"),

    # Individual comments
    path("comments/", CommentListCreateView.as_view(), name="comment-list-create"),
    path("comments/<int:comment_id>/", CommentDetailView.as_view(), name="comment-detail"),

    # Pods
    path("pods/", PodListCreateView.as_view(), name="pod-list-create"),
    path("pods/<int:pod_id>/", PodDetailView.as_view(), name="pod-detail"),

    # Pod memberships
    path("pod-memberships/", PodMembershipListCreateView.as_view(), name="pod-membership-list-create"),
    path("pod-memberships/<int:membership_id>/accept/", PodMembershipAcceptView.as_view(), name="pod-membership-accept"),
    path("pod-memberships/<int:membership_id>/decline/", PodMembershipDeclineView.as_view(), name="pod-membership-decline"),

    path(
        "pod-memberships/<int:membership_id>/role/",
        PodMembershipRoleUpdateView.as_view(),
        name="pod-membership-role-update",
    ),
    path(
        "pod-memberships/<int:membership_id>/remove/",
        PodMembershipRemoveView.as_view(),
        name="pod-membership-remove",
    ),
    path(
        "pod-memberships/<int:membership_id>/cancel/",
        PodMembershipCancelView.as_view(),
        name="pod-membership-cancel",
    ),
    path(
        "pod-memberships/<int:membership_id>/resend/",
        PodMembershipResendView.as_view(),
        name="pod-membership-resend",
    ),

    # Pod goals
    path("pod-goals/", PodGoalListCreateView.as_view(), name="pod-goal-list-create"),
    path("pod-goals/<int:pod_goal_id>/", PodGoalDetailView.as_view(), name="pod-goal-detail"),

    # Pod check-ins
    path("pod-checkins/", PodCheckInListCreateView.as_view(), name="pod-checkin-list-create"),
    path("pod-checkins/<int:checkin_id>/", PodCheckInDetailView.as_view(), name="pod-checkin-detail"),
    path("pod-checkins/<int:checkin_id>/approve/", PodCheckInApproveView.as_view(), name="pod-checkin-approve"),
    path("pod-checkins/<int:checkin_id>/reject/", PodCheckInRejectView.as_view(), name="pod-checkin-reject"),

    # Pod comments
    path("pod-comments/", PodCommentListCreateView.as_view(), name="pod-comment-list-create"),
    path("pod-comments/<int:comment_id>/", PodCommentDetailView.as_view(), name="pod-comment-detail"),

    # Pod Invite Candidate View
    path(
    "pods/<int:pod_id>/invite-candidates/",
    PodInviteCandidateView.as_view(),
    name="pod-invite-candidates",
),

    # User Search
    path("users/search/", UserSearchView.as_view(), name="user-search"),
    
    # Connections
    path("connections/", ConnectionListCreateView.as_view(), name="connection-list-create"),
    path("connections/<int:connection_id>/accept/", ConnectionAcceptView.as_view(), name="connection-accept"),
    path("connections/<int:connection_id>/decline/", ConnectionDeclineView.as_view(), name="connection-decline"),

    # Notifications
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/summary/", NotificationSummaryView.as_view(), name="notification-summary"),
    path("notifications/read-all/", NotificationMarkAllReadView.as_view(), name="notification-read-all"),
    path("notifications/<int:notification_id>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("notifications/<int:notification_id>/unread/", NotificationMarkUnreadView.as_view(), name="notification-mark-unread"),
    path("notifications/<int:notification_id>/resolve/", NotificationResolveView.as_view(), name="notification-resolve"),

    # QR connection invites
    path(
        "connection-invites/qr/",
        ConnectionQrInviteCreateView.as_view(),
        name="connection-qr-invite-create",
    ),
    path(
        "connection-invites/qr/<uuid:token>/claim/",
        ConnectionQrInviteClaimView.as_view(),
        name="connection-qr-invite-claim",
    ),
]