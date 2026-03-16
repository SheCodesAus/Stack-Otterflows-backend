from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Pod,
    PodMembership,
    PodGoal,
    PodCheckIn,
    Connection,
    Goal,
    GoalAssignment,
    CheckIn,
    Comment,
    PodComment,
    Notification,
)

from .permissions import (
    is_active_member,
    is_goal_owner,
    can_view_goal,
    can_verify_individual_checkin,
)

from .serializers import (
    PodSerializer,
    PodGoalSerializer,
    PodCheckInSerializer,
    ConnectionSerializer,
    GoalSerializer,
    GoalAssignmentSerializer,
    CheckInSerializer,
    CommentSerializer,
    PodCommentSerializer,
    GoalDetailSerializer,
    PodDetailSerializer,
    CheckInDetailSerializer,
    PodCheckInDetailSerializer,
    NotificationSerializer,
    UserSearchSerializer,
    PodMembershipDetailSerializer,
    PodInviteCandidateSerializer,
)

from .services import (
    create_notification,
    create_bulk_notifications,
    resolve_notifications,
)

User = get_user_model()
# ------------------------------------------------------------
# INDIVIDUAL GOALS
# ------------------------------------------------------------

class GoalListCreateView(APIView):
    """
    GET  /api/goals/ -> list my goals
    POST /api/goals/ -> create a goal
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        goals = Goal.objects.filter(owner=request.user).order_by("-created_at")
        return Response(GoalSerializer(goals, many=True).data)

    def post(self, request):
        serializer = GoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goal = serializer.save(owner=request.user)
        return Response(GoalSerializer(goal).data, status=status.HTTP_201_CREATED)


class GoalDetailView(APIView):
    """
    GET    /api/goals/<goal_id>/   -> retrieve one goal
    PATCH  /api/goals/<goal_id>/   -> update one goal (owner only)
    DELETE /api/goals/<goal_id>/   -> delete one goal (owner only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, goal_id):
        goal = get_object_or_404(
            Goal.objects.prefetch_related(
                "assignments__buddy",
                "checkins__created_by",
                "checkins__verified_by",
                "comments__author",
            ),
            id=goal_id,
        )

        if not can_view_goal(request.user, goal):
            return Response(
                {"detail": "You do not have permission to view this goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(GoalDetailSerializer(goal).data)

    def patch(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id)

        if not is_goal_owner(request.user, goal):
            return Response(
                {"detail": "Only the goal owner can update this goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GoalSerializer(goal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id)

        if not is_goal_owner(request.user, goal):
            return Response(
                {"detail": "Only the goal owner can delete this goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        goal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ------------------------------------------------------------
# GOAL ASSIGNMENTS
# ------------------------------------------------------------

class GoalAssignmentListCreateView(APIView):
    """
    GET  /api/goal-assignments/?goal=<goal_id>
         -> owner views assignments for a goal

    GET  /api/goal-assignments/
         -> list assignments where I am the buddy

    POST /api/goal-assignments/
         -> create assignment request
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        goal_id = request.query_params.get("goal")

        if goal_id:
            goal = get_object_or_404(Goal, id=goal_id)

            if not is_goal_owner(request.user, goal):
                return Response(
                    {"detail": "Only the goal owner can view assignments."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            assignments = GoalAssignment.objects.filter(goal=goal).order_by("-created_at")
            return Response(GoalAssignmentSerializer(assignments, many=True).data)

        assignments = GoalAssignment.objects.filter(buddy=request.user).order_by("-created_at")
        return Response(GoalAssignmentSerializer(assignments, many=True).data)

    def post(self, request):
        serializer = GoalAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goal = serializer.validated_data["goal"]
        buddy = serializer.validated_data["buddy"]

        if not is_goal_owner(request.user, goal):
            return Response(
                {"detail": "Only the goal owner can assign buddies."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if buddy == request.user:
            return Response(
                {"detail": "You cannot assign yourself as your own buddy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_connected = Connection.objects.filter(
            status="ACCEPTED"
        ).filter(
            Q(inviter=request.user, invitee=buddy) |
            Q(inviter=buddy, invitee=request.user)
        ).exists()

        if not is_connected:
            return Response(
                {"detail": "You can only assign an accepted connection as a buddy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            assignment = GoalAssignment.objects.create(
                goal=goal,
                buddy=buddy,
                consent_status="PENDING",
            )
        except IntegrityError:
            return Response(
                {"detail": "That user is already assigned to this goal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_notification(
            recipient=buddy,
            notif_type="GOAL_ASSIGNMENT_REQUEST",
            actor=request.user,
            payload={
                "goal_id": goal.id,
                "goal_title": goal.title,
                "assignment_id": assignment.id,
            },
        )

        return Response(
            GoalAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class GoalAssignmentAcceptView(APIView):
    """
    POST /api/goal-assignments/<assignment_id>/accept/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        assignment = get_object_or_404(GoalAssignment, id=assignment_id)

        if assignment.buddy_id != request.user.id:
            return Response(
                {"detail": "You can only accept your own assignment request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if assignment.consent_status != "PENDING":
            return Response(
                {"detail": "Only pending assignments can be accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.accept()

        create_notification(
            recipient=assignment.goal.owner,
            notif_type="GOAL_ASSIGNMENT_ACCEPTED",
            actor=request.user,
            payload={
                "goal_id": assignment.goal.id,
                "goal_title": assignment.goal.title,
                "assignment_id": assignment.id,
            },
        )

        resolve_notifications(
            recipient=request.user,
            notif_types=["GOAL_ASSIGNMENT_REQUEST"],
            payload_filters={"assignment_id": assignment.id},
        )

        return Response({"detail": "Assignment accepted."})


class GoalAssignmentDeclineView(APIView):
    """
    POST /api/goal-assignments/<assignment_id>/decline/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        assignment = get_object_or_404(GoalAssignment, id=assignment_id)

        if assignment.buddy_id != request.user.id:
            return Response(
                {"detail": "You can only decline your own assignment request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if assignment.consent_status != "PENDING":
            return Response(
                {"detail": "Only pending assignments can be declined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.decline()

        create_notification(
            recipient=assignment.goal.owner,
            notif_type="GOAL_ASSIGNMENT_DECLINED",
            actor=request.user,
            payload={
                "goal_id": assignment.goal.id,
                "goal_title": assignment.goal.title,
                "assignment_id": assignment.id,
            },
        )
        
        resolve_notifications(
            recipient=request.user,
            notif_types=["GOAL_ASSIGNMENT_REQUEST"],
            payload_filters={"assignment_id": assignment.id},
        )

        return Response({"detail": "Assignment declined."})


# ------------------------------------------------------------
# INDIVIDUAL CHECK-INS
# ------------------------------------------------------------

class CheckInListCreateView(APIView):
    """
    GET  /api/checkins/?goal=<goal_id>
    POST /api/checkins/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        goal_id = request.query_params.get("goal")
        if not goal_id:
            return Response(
                {"detail": "Provide ?goal=<goal_id>"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        goal = get_object_or_404(Goal, id=goal_id)

        if not can_view_goal(request.user, goal):
            return Response(
                {"detail": "You do not have permission to view this goal's check-ins."},
                status=status.HTTP_403_FORBIDDEN,
            )

        checkins = CheckIn.objects.filter(goal=goal).order_by("-created_at")
        return Response(CheckInSerializer(checkins, many=True).data)

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goal = serializer.validated_data["goal"]

        if not is_goal_owner(request.user, goal):
            return Response(
                {"detail": "Only the goal owner can create check-ins."},
                status=status.HTTP_403_FORBIDDEN,
            )

        checkin = serializer.save(created_by=request.user)

        accepted_buddies = [
            assignment.buddy
            for assignment in GoalAssignment.objects.filter(
                goal=goal,
                consent_status="ACCEPTED",
            ).select_related("buddy")
        ]

        create_bulk_notifications(
            recipients=accepted_buddies,
            notif_type="CHECKIN_SUBMITTED",
            actor=request.user,
            payload={
                "goal_id": goal.id,
                "goal_title": goal.title,
                "checkin_id": checkin.id,
            },
        )

        return Response(CheckInSerializer(checkin).data, status=status.HTTP_201_CREATED)


class CheckInApproveView(APIView):
    """
    POST /api/checkins/<checkin_id>/approve/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, checkin_id):
        checkin = get_object_or_404(CheckIn, id=checkin_id)

        if not can_verify_individual_checkin(request.user, checkin):
            return Response(
                {"detail": "You do not have permission to approve this check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending check-ins can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkin.approve(request.user)

        create_notification(
            recipient=checkin.created_by,
            notif_type="CHECKIN_APPROVED",
            actor=request.user,
            payload={
                "goal_id": checkin.goal.id,
                "goal_title": checkin.goal.title,
                "checkin_id": checkin.id,
            },
        )

        accepted_buddies = [
            assignment.buddy
            for assignment in GoalAssignment.objects.filter(
                goal=checkin.goal,
                consent_status="ACCEPTED",
            ).select_related("buddy")
        ]

        resolve_notifications(
            recipients=accepted_buddies,
            notif_types=["CHECKIN_SUBMITTED"],
            payload_filters={"checkin_id": checkin.id},
        )

        return Response({"detail": "Approved."})


class CheckInRejectView(APIView):
    """
    POST /api/checkins/<checkin_id>/reject/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, checkin_id):
        checkin = get_object_or_404(CheckIn, id=checkin_id)

        if not can_verify_individual_checkin(request.user, checkin):
            return Response(
                {"detail": "You do not have permission to reject this check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending check-ins can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = (request.data.get("reason") or "").strip()
        checkin.reject(request.user, reason)

        create_notification(
            recipient=checkin.created_by,
            notif_type="CHECKIN_REJECTED",
            actor=request.user,
            payload={
                "goal_id": checkin.goal.id,
                "goal_title": checkin.goal.title,
                "checkin_id": checkin.id,
                "reason": reason,
            },
        )

        accepted_buddies = [
            assignment.buddy
            for assignment in GoalAssignment.objects.filter(
                goal=checkin.goal,
                consent_status="ACCEPTED",
            ).select_related("buddy")
        ]

        resolve_notifications(
            recipients=accepted_buddies,
            notif_types=["CHECKIN_SUBMITTED"],
            payload_filters={"checkin_id": checkin.id},
        )

        return Response({"detail": "Rejected.", "reason": reason})

class CheckInDetailView(APIView):
    """
    GET    /api/checkins/<checkin_id>/   -> retrieve one check-in
    PATCH  /api/checkins/<checkin_id>/   -> update one check-in (creator only, pending only)
    DELETE /api/checkins/<checkin_id>/   -> delete one check-in (creator only, pending only)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, checkin_id):
        checkin = get_object_or_404(CheckIn, id=checkin_id)

        if not can_view_goal(request.user, checkin.goal):
            return Response(
                {"detail": "You do not have permission to view this check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(CheckInDetailSerializer(checkin).data)

    def patch(self, request, checkin_id):
        checkin = get_object_or_404(CheckIn, id=checkin_id)

        if checkin.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the creator can update this check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending check-ins can be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CheckInSerializer(checkin, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self, request, checkin_id):
        checkin = get_object_or_404(CheckIn, id=checkin_id)

        if checkin.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the creator can delete this check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending check-ins can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        accepted_buddies = [
            assignment.buddy
            for assignment in GoalAssignment.objects.filter(
                goal=checkin.goal,
                consent_status="ACCEPTED",
            ).select_related("buddy")
        ]

        checkin_id_value = checkin.id
        checkin.delete()

        resolve_notifications(
            recipients=accepted_buddies,
            notif_types=["CHECKIN_SUBMITTED"],
            payload_filters={"checkin_id": checkin_id_value},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

# ------------------------------------------------------------
# INDIVIDUAL COMMENTS
# ------------------------------------------------------------

class CommentListCreateView(APIView):
    """
    GET  /api/comments/?goal=<goal_id>
    POST /api/comments/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        goal_id = request.query_params.get("goal")
        if not goal_id:
            return Response(
                {"detail": "Provide ?goal=<goal_id>"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        goal = get_object_or_404(Goal, id=goal_id)

        if not can_view_goal(request.user, goal):
            return Response(
                {"detail": "You do not have permission to view comments for this goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments = Comment.objects.filter(goal=goal).order_by("-created_at")
        return Response(CommentSerializer(comments, many=True).data)

    def post(self, request):
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goal = serializer.validated_data["goal"]
        checkin = serializer.validated_data.get("checkin")

        if not can_view_goal(request.user, goal):
            return Response(
                {"detail": "You do not have permission to comment on this goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin and checkin.goal_id != goal.id:
            return Response(
                {"detail": "That check-in does not belong to this goal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = serializer.save(author=request.user)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDetailView(APIView):
    """
    PATCH  /api/comments/<comment_id>/   -> update one comment (author only)
    DELETE /api/comments/<comment_id>/   -> delete one comment
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)

        if not can_view_goal(request.user, comment.goal):
            return Response(
                {"detail": "You do not have permission to access this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if comment.author_id != request.user.id:
            return Response(
                {"detail": "Only the comment author can edit this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        allowed_fields = {"kind", "body"}
        incoming_fields = set(request.data.keys())

        invalid_fields = incoming_fields - allowed_fields
        if invalid_fields:
            return Response(
                {
                    "detail": "Only 'kind' and 'body' can be updated.",
                    "invalid_fields": sorted(list(invalid_fields)),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CommentSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(CommentSerializer(comment).data)

    def delete(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)

        if not can_view_goal(request.user, comment.goal):
            return Response(
                {"detail": "You do not have permission to access this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if comment.author_id != request.user.id and not is_goal_owner(request.user, comment.goal):
            return Response(
                {"detail": "You do not have permission to delete this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------
# PODS
# ------------------------------------------------------------

class PodListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        return (
            Pod.objects.filter(
                memberships__user=request.user,
                memberships__status="ACTIVE",
            )
            .annotate(
                member_count=Count(
                    "memberships",
                    filter=Q(memberships__status="ACTIVE"),
                    distinct=True,
                ),
                active_goal_count=Count(
                    "goals",
                    filter=Q(goals__status="ACTIVE"),
                    distinct=True,
                ),
            )
            .distinct()
        )

    def get(self, request):
        pods = self.get_queryset(request)
        return Response(PodSerializer(pods, many=True).data)

    def post(self, request):
        serializer = PodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod = serializer.save(created_by=request.user)
        PodMembership.objects.create(
            pod=pod,
            user=request.user,
            role="OWNER",
            status="ACTIVE",
            invited_by=request.user,
        )

        pod = self.get_queryset(request).get(pk=pod.pk)
        return Response(PodSerializer(pod).data, status=status.HTTP_201_CREATED)


class PodDetailView(APIView):
    """
    GET    /api/pods/<pod_id>/ -> retrieve pod
    PATCH  /api/pods/<pod_id>/ -> update pod
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pod_id):
        return get_object_or_404(
            Pod.objects.prefetch_related(
                "memberships__user",
                "goals__created_by",
                "goals__checkins__created_by",
                "goals__checkins__verified_by",
                "goals__comments__author",
            ),
            id=pod_id,
        )

    def get(self, request, pod_id):
        pod = self.get_object(pod_id)

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(PodDetailSerializer(pod).data)

    def patch(self, request, pod_id):
        pod = get_object_or_404(Pod, id=pod_id)

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership = PodMembership.objects.filter(
            pod=pod,
            user=request.user,
            status="ACTIVE",
        ).first()

        if not membership or membership.role not in ["OWNER", "ADMIN"]:
            return Response(
                {"detail": "Only pod owners or admins can update this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PodSerializer(pod, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(PodSerializer(pod).data)

# ------------------------------------------------------------
# POD MEMBERSHIPS
# ------------------------------------------------------------


class PodMembershipListCreateView(APIView):
    """
    GET  /api/pod-memberships/?pod=<pod_id>
         -> list memberships for a pod

    GET  /api/pod-memberships/
         -> list my own pod memberships / invites

    POST /api/pod-memberships/
         -> invite/add a member by user id
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pod_id = request.query_params.get("pod")

        if pod_id:
            pod = get_object_or_404(Pod, id=pod_id)

            if not is_active_member(request.user, pod):
                return Response(
                    {"detail": "You are not an ACTIVE member of this pod."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            memberships = PodMembership.objects.filter(pod=pod).order_by("-created_at")
            return Response(PodMembershipDetailSerializer(memberships, many=True).data)

        memberships = PodMembership.objects.filter(user=request.user).order_by("-created_at")
        return Response(PodMembershipDetailSerializer(memberships, many=True).data)

    def post(self, request):
        pod_id = request.data.get("pod")
        invited_user_id = request.data.get("user")

        if not pod_id or not invited_user_id:
            return Response(
                {"detail": "Both pod and user are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pod = get_object_or_404(Pod, id=pod_id)
        invited_user = get_object_or_404(User, id=invited_user_id)

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "Only ACTIVE members can invite others."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if invited_user == request.user:
            return Response(
                {"detail": "You cannot invite yourself to a pod."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_connected = Connection.objects.filter(
            (
                Q(inviter=request.user, invitee=invited_user)
                | Q(inviter=invited_user, invitee=request.user)
            ),
            status="ACCEPTED",
        ).exists()

        if not is_connected:
            return Response(
                {"detail": "You can only invite accepted connections into a pod."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_membership = PodMembership.objects.filter(
            pod=pod,
            user=invited_user,
        ).first()

        if existing_membership:
            if existing_membership.status in ["DECLINED", "LEFT", "REMOVED"]:
                existing_membership.status = "INVITED"
                existing_membership.role = "MEMBER"
                existing_membership.invited_by = request.user
                existing_membership.responded_at = None
                existing_membership.save(
                    update_fields=["status", "role", "invited_by", "responded_at"]
                )
                membership = existing_membership
            else:
                return Response(
                    {"detail": "That user already has an active or pending membership for this pod."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            membership = PodMembership.objects.create(
                pod=pod,
                user=invited_user,
                invited_by=request.user,
                status="INVITED",
                role="MEMBER",
            )

        create_notification(
            recipient=invited_user,
            notif_type="POD_INVITE",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "membership_id": membership.id,
                "target_url": "/notifications",
            },
        )

        return Response(
            PodMembershipDetailSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class PodMembershipAcceptView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/accept/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        membership = get_object_or_404(PodMembership, id=membership_id)

        if membership.user_id != request.user.id:
            return Response(
                {"detail": "You can only accept your own invite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.status != "INVITED":
            return Response(
                {"detail": "Only invited memberships can be accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.accept()

        pod = membership.pod

        active_members_to_notify = [
            pod_membership.user
            for pod_membership in PodMembership.objects.filter(
                pod=pod,
                status="ACTIVE",
            ).select_related("user")
            if pod_membership.user_id != request.user.id
        ]

        create_bulk_notifications(
            recipients=active_members_to_notify,
            notif_type="POD_MEMBER_JOINED",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "membership_id": membership.id,
                "target_url": f"/pods/{pod.id}",
            },
        )

        resolve_notifications(
            recipient=request.user,
            notif_types=["POD_INVITE"],
            payload_filters={"membership_id": membership.id},
        )

        return Response({"detail": "Membership accepted."})


class PodMembershipDeclineView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/decline/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        membership = get_object_or_404(PodMembership, id=membership_id)

        if membership.user_id != request.user.id:
            return Response(
                {"detail": "You can only decline your own invite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.status != "INVITED":
            return Response(
                {"detail": "Only invited memberships can be declined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.decline()

        pod = membership.pod

        resolve_notifications(
            recipient=request.user,
            notif_types=["POD_INVITE"],
            payload_filters={"membership_id": membership.id},
        )

        # Only keep this block if you added POD_INVITE_DECLINED to NOTIF_TYPE.
        create_notification(
            recipient=membership.invited_by,
            notif_type="POD_INVITE_DECLINED",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "membership_id": membership.id,
                "target_url": f"/pods/{pod.id}",
            },
        )

        return Response({"detail": "Membership declined."})
    
class PodMembershipRoleUpdateView(APIView):
    """
    PATCH /api/pod-memberships/<membership_id>/role/

    Body:
    {
        "role": "ADMIN"   # or "MEMBER"
    }

    Rules:
    - only ACTIVE pod owners can change roles
    - only ACTIVE memberships can be changed
    - cannot change an OWNER with this endpoint
    - cannot change your own role with this endpoint
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, membership_id):
        membership = get_object_or_404(
            PodMembership.objects.select_related("pod", "user"),
            id=membership_id,
        )
        pod = membership.pod

        acting_membership = PodMembership.objects.filter(
            pod=pod,
            user=request.user,
            status="ACTIVE",
        ).first()

        if not acting_membership:
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if acting_membership.role != "OWNER":
            return Response(
                {"detail": "Only pod owners can change member roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.status != "ACTIVE":
            return Response(
                {"detail": "Only ACTIVE memberships can have roles updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.user_id == request.user.id:
            return Response(
                {"detail": "You cannot change your own role here."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.role == "OWNER":
            return Response(
                {"detail": "Owner roles must be changed through a separate ownership transfer flow."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_role = (request.data.get("role") or "").strip().upper()

        if new_role not in ["ADMIN", "MEMBER"]:
            return Response(
                {"detail": "Role must be either ADMIN or MEMBER."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.role == new_role:
            return Response(PodMembershipDetailSerializer(membership).data)

        membership.role = new_role
        membership.save(update_fields=["role"])

        return Response(PodMembershipDetailSerializer(membership).data)

class PodMembershipRemoveView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/remove/

    Rules:
    - ACTIVE owners/admins can remove people
    - admins can only remove MEMBER roles
    - owners can remove ADMIN or MEMBER roles
    - cannot remove an OWNER with this endpoint
    - cannot remove yourself here
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        membership = get_object_or_404(
            PodMembership.objects.select_related("pod", "user"),
            id=membership_id,
        )
        pod = membership.pod

        acting_membership = PodMembership.objects.filter(
            pod=pod,
            user=request.user,
            status="ACTIVE",
        ).first()

        if not acting_membership:
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if acting_membership.role not in ["OWNER", "ADMIN"]:
            return Response(
                {"detail": "Only pod owners or admins can remove members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.status != "ACTIVE":
            return Response(
                {"detail": "Only ACTIVE members can be removed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.user_id == request.user.id:
            return Response(
                {"detail": "You cannot remove yourself with this endpoint. Use a leave-pod flow instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.role == "OWNER":
            return Response(
                {"detail": "Owners cannot be removed here. Transfer ownership first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if acting_membership.role == "ADMIN" and membership.role != "MEMBER":
            return Response(
                {"detail": "Admins can only remove members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership.status = "REMOVED"
        membership.responded_at = timezone.now()
        membership.save(update_fields=["status", "responded_at"])

        return Response(PodMembershipDetailSerializer(membership).data)
    
class PodMembershipCancelView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/cancel/

    Rules:
    - ACTIVE owners/admins can cancel pending invites
    - only INVITED memberships can be cancelled
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        membership = get_object_or_404(
            PodMembership.objects.select_related("pod", "user"),
            id=membership_id,
        )
        pod = membership.pod

        acting_membership = PodMembership.objects.filter(
            pod=pod,
            user=request.user,
            status="ACTIVE",
        ).first()

        if not acting_membership:
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if acting_membership.role not in ["OWNER", "ADMIN"]:
            return Response(
                {"detail": "Only pod owners or admins can cancel invites."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.status != "INVITED":
            return Response(
                {"detail": "Only pending invites can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.status = "REMOVED"
        membership.responded_at = timezone.now()
        membership.save(update_fields=["status", "responded_at"])

        resolve_notifications(
            recipient=membership.user,
            notif_types=["POD_INVITE"],
            payload_filters={"membership_id": membership.id},
        )

        return Response(PodMembershipDetailSerializer(membership).data)
    
class PodMembershipResendView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/resend/

    Rules:
    - ACTIVE owners/admins can resend pending invites
    - only INVITED memberships can be resent
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        membership = get_object_or_404(
            PodMembership.objects.select_related("pod", "user"),
            id=membership_id,
        )
        pod = membership.pod

        acting_membership = PodMembership.objects.filter(
            pod=pod,
            user=request.user,
            status="ACTIVE",
        ).first()

        if not acting_membership:
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if acting_membership.role not in ["OWNER", "ADMIN"]:
            return Response(
                {"detail": "Only pod owners or admins can resend invites."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.status != "INVITED":
            return Response(
                {"detail": "Only pending invites can be resent."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.invited_by = request.user
        membership.responded_at = None
        membership.save(update_fields=["invited_by", "responded_at"])

        resolve_notifications(
            recipient=membership.user,
            notif_types=["POD_INVITE"],
            payload_filters={"membership_id": membership.id},
        )

        create_notification(
            recipient=membership.user,
            notif_type="POD_INVITE",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "membership_id": membership.id,
                "target_url": "/notifications",
            },
        )

        return Response(PodMembershipDetailSerializer(membership).data)    
# ------------------------------------------------------------
# POD GOALS
# ------------------------------------------------------------

class PodGoalListCreateView(APIView):
    """
    GET  /api/pod-goals/?pod=<pod_id> -> list goals in pod
    POST /api/pod-goals/              -> create pod goal
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pod_id = request.query_params.get("pod")
        if not pod_id:
            return Response(
                {"detail": "Provide ?pod=<pod_id>"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pod = get_object_or_404(Pod, id=pod_id)

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        goals = PodGoal.objects.filter(pod=pod).order_by("-created_at")
        return Response(PodGoalSerializer(goals, many=True).data)

    def post(self, request):
        serializer = PodGoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod = serializer.validated_data["pod"]

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "Only ACTIVE members can create pod goals."},
                status=status.HTTP_403_FORBIDDEN,
            )

        goal = serializer.save(created_by=request.user)

        active_members_to_notify = [
            membership.user
            for membership in PodMembership.objects.filter(
                pod=pod,
                status="ACTIVE",
            ).select_related("user")
            if membership.user_id != request.user.id
        ]

        create_bulk_notifications(
            recipients=active_members_to_notify,
            notif_type="POD_GOAL_CREATED",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "pod_goal_id": goal.id,
                "pod_goal_title": getattr(goal, "title", None),
                "target_url": f"/pods/{pod.id}/goals/{goal.id}",
            },
        )

        return Response(PodGoalSerializer(goal).data, status=status.HTTP_201_CREATED)


class PodGoalDetailView(APIView):
    """
    GET    /api/pod-goals/<pod_goal_id>/   -> retrieve one pod goal
    PATCH  /api/pod-goals/<pod_goal_id>/   -> update one pod goal
    DELETE /api/pod-goals/<pod_goal_id>/   -> delete one pod goal
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pod_goal_id):
        pod_goal = get_object_or_404(PodGoal, id=pod_goal_id)

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(PodGoalSerializer(pod_goal).data)

    def patch(self, request, pod_goal_id):
        pod_goal = get_object_or_404(PodGoal, id=pod_goal_id)

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if pod_goal.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the creator can update this pod goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PodGoalSerializer(pod_goal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self, request, pod_goal_id):
        pod_goal = get_object_or_404(PodGoal, id=pod_goal_id)

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if pod_goal.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the creator can delete this pod goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        pod_goal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------
# POD CHECK-INS
# ------------------------------------------------------------

class PodCheckInListCreateView(APIView):
    """
    GET  /api/pod-checkins/?pod_goal=<pod_goal_id> -> list check-ins for a goal
    POST /api/pod-checkins/                        -> create check-in
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pod_goal_id = request.query_params.get("pod_goal")
        if not pod_goal_id:
            return Response(
                {"detail": "Provide ?pod_goal=<pod_goal_id>"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pod_goal = get_object_or_404(PodGoal, id=pod_goal_id)

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        checkins = PodCheckIn.objects.filter(pod_goal=pod_goal).order_by("-created_at")
        return Response(PodCheckInSerializer(checkins, many=True).data)

    def post(self, request):
        serializer = PodCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod_goal = serializer.validated_data["pod_goal"]

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "Only ACTIVE members can submit check-ins."},
                status=status.HTTP_403_FORBIDDEN,
            )

        checkin = serializer.save(created_by=request.user)
        pod = pod_goal.pod

        active_reviewers = [
            membership.user
            for membership in PodMembership.objects.filter(
                pod=pod,
                status="ACTIVE",
            ).select_related("user")
            if membership.user_id != request.user.id
        ]

        create_bulk_notifications(
            recipients=active_reviewers,
            notif_type="POD_CHECKIN_SUBMITTED",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "pod_goal_id": pod_goal.id,
                "pod_goal_title": getattr(pod_goal, "title", None),
                "pod_checkin_id": checkin.id,
                "target_url": f"/pods/{pod.id}/goals/{pod_goal.id}",
            },
        )

        return Response(
            PodCheckInSerializer(checkin).data,
            status=status.HTTP_201_CREATED,
        )


class PodCheckInApproveView(APIView):
    """
    POST /api/pod-checkins/<checkin_id>/approve/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, checkin_id):
        checkin = get_object_or_404(PodCheckIn, id=checkin_id)
        pod = checkin.pod_goal.pod

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.created_by_id == request.user.id:
            return Response(
                {"detail": "You cannot verify your own check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending check-ins can be verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkin.approve(request.user)

        create_notification(
            recipient=checkin.created_by,
            notif_type="POD_CHECKIN_APPROVED",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "pod_goal_id": checkin.pod_goal.id,
                "pod_goal_title": getattr(checkin.pod_goal, "title", None),
                "pod_checkin_id": checkin.id,
                "target_url": f"/pods/{pod.id}/goals/{checkin.pod_goal.id}",
            },
        )

        active_reviewers = [
            membership.user
            for membership in PodMembership.objects.filter(
                pod=pod,
                status="ACTIVE",
            ).select_related("user")
            if membership.user_id != checkin.created_by_id
        ]

        resolve_notifications(
            recipients=active_reviewers,
            notif_types=["POD_CHECKIN_SUBMITTED"],
            payload_filters={"pod_checkin_id": checkin.id},
        )

        return Response({"detail": "Approved."})


class PodCheckInRejectView(APIView):
    """
    POST /api/pod-checkins/<checkin_id>/reject/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, checkin_id):
        checkin = get_object_or_404(PodCheckIn, id=checkin_id)
        pod = checkin.pod_goal.pod

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.created_by_id == request.user.id:
            return Response(
                {"detail": "You cannot verify your own check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending check-ins can be verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = (request.data.get("reason") or "").strip()
        checkin.reject(request.user, reason)

        create_notification(
            recipient=checkin.created_by,
            notif_type="POD_CHECKIN_REJECTED",
            actor=request.user,
            payload={
                "pod_id": pod.id,
                "pod_name": getattr(pod, "name", None) or getattr(pod, "title", None),
                "pod_goal_id": checkin.pod_goal.id,
                "pod_goal_title": getattr(checkin.pod_goal, "title", None),
                "pod_checkin_id": checkin.id,
                "reason": reason,
                "target_url": f"/pods/{pod.id}/goals/{checkin.pod_goal.id}",
            },
        )

        active_reviewers = [
            membership.user
            for membership in PodMembership.objects.filter(
                pod=pod,
                status="ACTIVE",
            ).select_related("user")
            if membership.user_id != checkin.created_by_id
        ]

        resolve_notifications(
            recipients=active_reviewers,
            notif_types=["POD_CHECKIN_SUBMITTED"],
            payload_filters={"pod_checkin_id": checkin.id},
        )

        return Response({"detail": "Rejected.", "reason": reason})


class PodCheckInDetailView(APIView):
    """
    GET    /api/pod-checkins/<checkin_id>/   -> retrieve one pod check-in
    PATCH  /api/pod-checkins/<checkin_id>/   -> update one pod check-in (creator only, pending only)
    DELETE /api/pod-checkins/<checkin_id>/   -> delete one pod check-in (creator only, pending only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, checkin_id):
        checkin = get_object_or_404(PodCheckIn, id=checkin_id)

        if not is_active_member(request.user, checkin.pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(PodCheckInDetailSerializer(checkin).data)

    def patch(self, request, checkin_id):
        checkin = get_object_or_404(PodCheckIn, id=checkin_id)

        if not is_active_member(request.user, checkin.pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the creator can update this pod check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending pod check-ins can be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PodCheckInSerializer(checkin, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self, request, checkin_id):
        checkin = get_object_or_404(PodCheckIn, id=checkin_id)

        if not is_active_member(request.user, checkin.pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.created_by_id != request.user.id:
            return Response(
                {"detail": "Only the creator can delete this pod check-in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin.status != "PENDING":
            return Response(
                {"detail": "Only pending pod check-ins can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pod = checkin.pod_goal.pod

        active_reviewers = [
            membership.user
            for membership in PodMembership.objects.filter(
                pod=pod,
                status="ACTIVE",
            ).select_related("user")
            if membership.user_id != checkin.created_by_id
        ]

        checkin_id_value = checkin.id
        checkin.delete()

        resolve_notifications(
            recipients=active_reviewers,
            notif_types=["POD_CHECKIN_SUBMITTED"],
            payload_filters={"pod_checkin_id": checkin_id_value},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

# ------------------------------------------------------------
# POD COMMENTS
# ------------------------------------------------------------

class PodCommentListCreateView(APIView):
    """
    GET  /api/pod-comments/?pod_goal=<pod_goal_id>
    POST /api/pod-comments/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pod_goal_id = request.query_params.get("pod_goal")
        if not pod_goal_id:
            return Response(
                {"detail": "Provide ?pod_goal=<pod_goal_id>"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pod_goal = get_object_or_404(PodGoal, id=pod_goal_id)

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comments = PodComment.objects.filter(pod_goal=pod_goal).order_by("-created_at")
        return Response(PodCommentSerializer(comments, many=True).data)

    def post(self, request):
        serializer = PodCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod_goal = serializer.validated_data["pod_goal"]
        checkin = serializer.validated_data.get("checkin")

        if not is_active_member(request.user, pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if checkin and checkin.pod_goal_id != pod_goal.id:
            return Response(
                {"detail": "That pod check-in does not belong to this pod goal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = serializer.save(author=request.user)
        return Response(PodCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class PodCommentDetailView(APIView):
    """
    PATCH  /api/pod-comments/<comment_id>/   -> update one pod comment (author only)
    DELETE /api/pod-comments/<comment_id>/   -> delete one pod comment
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, comment_id):
        comment = get_object_or_404(PodComment, id=comment_id)

        if not is_active_member(request.user, comment.pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if comment.author_id != request.user.id:
            return Response(
                {"detail": "Only the comment author can edit this pod comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        allowed_fields = {"kind", "body"}
        incoming_fields = set(request.data.keys())

        invalid_fields = incoming_fields - allowed_fields
        if invalid_fields:
            return Response(
                {
                    "detail": "Only 'kind' and 'body' can be updated.",
                    "invalid_fields": sorted(list(invalid_fields)),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PodCommentSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(PodCommentSerializer(comment).data)

    def delete(self, request, comment_id):
        comment = get_object_or_404(PodComment, id=comment_id)

        if not is_active_member(request.user, comment.pod_goal.pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if comment.author_id != request.user.id and comment.pod_goal.created_by_id != request.user.id:
            return Response(
                {"detail": "You do not have permission to delete this pod comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------
# CONNECTIONS
# ------------------------------------------------------------

class ConnectionListCreateView(APIView):
    """
    GET  /api/connections/ -> list my connection records
    POST /api/connections/ -> create a connection invite
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connections = Connection.objects.filter(
            Q(inviter=request.user) | Q(invitee=request.user)
        ).order_by("-created_at")

        return Response(ConnectionSerializer(connections, many=True).data)

    def post(self, request):
        serializer = ConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invitee = serializer.validated_data["invitee"]

        if invitee == request.user:
            return Response(
                {"detail": "You cannot connect with yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection = Connection(
            inviter=request.user,
            invitee=invitee,
            status="PENDING",
        )

        try:
            connection.full_clean()
            connection.save()
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            return Response(
                {"detail": "A connection between these users already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_notification(
            recipient=invitee,
            notif_type="CONNECTION_INVITE",
            actor=request.user,
            payload={
                "connection_id": connection.id,
                "target_url": "/connections",
            },
        )

        return Response(
            ConnectionSerializer(connection).data,
            status=status.HTTP_201_CREATED,
        )


class ConnectionAcceptView(APIView):
    """
    POST /api/connections/<connection_id>/accept/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id):
        connection = get_object_or_404(Connection, id=connection_id)

        if connection.invitee_id != request.user.id:
            return Response(
                {"detail": "You can only accept your own connection invite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if connection.status != "PENDING":
            return Response(
                {"detail": "Only pending connections can be accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection.accept()

        create_notification(
            recipient=connection.inviter,
            notif_type="CONNECTION_ACCEPTED",
            actor=request.user,
            payload={
                "connection_id": connection.id,
                "target_url": "/connections",
            },
        )

        resolve_notifications(
            recipient=request.user,
            notif_types=["CONNECTION_INVITE"],
            payload_filters={"connection_id": connection.id},
        )

        return Response({"detail": "Connection accepted."})


class ConnectionDeclineView(APIView):
    """
    POST /api/connections/<connection_id>/decline/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, connection_id):
        connection = get_object_or_404(Connection, id=connection_id)

        if connection.invitee_id != request.user.id:
            return Response(
                {"detail": "You can only decline your own connection invite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if connection.status != "PENDING":
            return Response(
                {"detail": "Only pending connections can be declined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection.decline()

        create_notification(
            recipient=connection.inviter,
            notif_type="CONNECTION_DECLINED",
            actor=request.user,
            payload={
                "connection_id": connection.id,
                "target_url": "/connections",
            },
        )

        resolve_notifications(
            recipient=request.user,
            notif_types=["CONNECTION_INVITE"],
            payload_filters={"connection_id": connection.id},
        )

        return Response({"detail": "Connection declined."})
    
# ------------------------------------------------------------
# NOTIFICATIONS
# ------------------------------------------------------------

VALID_NOTIFICATION_TABS = {"all", "unread", "needs_review"}


def apply_tab_filter(queryset, tab):
    if tab == "all":
        return queryset
    if tab == "unread":
        return queryset.unread()
    if tab == "needs_review":
        return queryset.needs_review()

    raise ValidationError(
        {"tab": "Invalid tab. Use 'all', 'unread', or 'needs_review'."}
    )


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Notification.objects.with_related()
            .for_user(self.request.user)
            .order_by("-created_at")
        )

        tab = self.request.query_params.get("tab", "all")
        queryset = apply_tab_filter(queryset, tab)

        limit = self.request.query_params.get("limit")
        if limit:
            try:
                limit = max(1, min(int(limit), 50))
            except ValueError:
                raise ValidationError({"limit": "Limit must be a whole number."})
            queryset = queryset[:limit]

        return queryset


class NotificationSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        base_queryset = Notification.objects.for_user(request.user)

        data = {
            "all_count": base_queryset.count(),
            "unread_count": base_queryset.unread().count(),
            "needs_review_count": base_queryset.needs_review().count(),
            "unread_needs_review_count": base_queryset.needs_review().unread().count(),
        }
        return Response(data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            recipient=request.user,
        )
        notification.mark_read()

        return Response(NotificationSerializer(notification).data)


class NotificationMarkUnreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            recipient=request.user,
        )
        notification.mark_unread()

        return Response(NotificationSerializer(notification).data)


class NotificationResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            recipient=request.user,
        )
        notification.mark_resolved(mark_read=True)

        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tab = request.data.get("tab", "all")
        queryset = Notification.objects.for_user(request.user)
        queryset = apply_tab_filter(queryset, tab)

        now = timezone.now()
        updated = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=now,
        )

        return Response(
            {
                "detail": "Notifications marked as read.",
                "updated_count": updated,
            }
        )
    
User = get_user_model()


class UserSearchView(APIView):
    """
    GET /api/users/search/?q=beck
    Returns users matching the search term, excluding:
    - the current user
    - users who already have any connection record with the current user
      (pending / accepted / declined / blocked)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()

        if len(query) < 2:
            return Response([])

        existing_connections = Connection.objects.filter(
            Q(inviter=request.user) | Q(invitee=request.user)
        )

        excluded_user_ids = set()

        for connection in existing_connections:
            if connection.inviter_id == request.user.id:
                excluded_user_ids.add(connection.invitee_id)
            else:
                excluded_user_ids.add(connection.inviter_id)

        searchable_fields = ["username", "first_name", "last_name", "email"]

        if any(field.name == "display_name" for field in User._meta.get_fields()):
            searchable_fields.append("display_name")

        filters = Q()
        for field in searchable_fields:
            filters |= Q(**{f"{field}__icontains": query})

        users = (
            User.objects.filter(filters)
            .exclude(id=request.user.id)
            .exclude(id__in=excluded_user_ids)
            .order_by("username")[:10]
        )

        return Response(UserSearchSerializer(users, many=True).data)
    


class PodInviteCandidateView(APIView):
    """
    GET /api/pods/<pod_id>/invite-candidates/?q=beck

    Returns accepted connections who can be invited into the pod.
    Excludes:
    - current user
    - users already ACTIVE in this pod
    - users already INVITED to this pod
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pod_id):
        pod = get_object_or_404(Pod, id=pod_id)

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = (request.query_params.get("q") or "").strip()

        if len(query) < 2:
            return Response([])

        searchable_fields = ["username", "first_name", "last_name", "email"]

        if any(field.name == "display_name" for field in User._meta.get_fields()):
            searchable_fields.append("display_name")

        filters = Q()
        for field in searchable_fields:
            filters |= Q(**{f"{field}__icontains": query})

        accepted_connections = Connection.objects.filter(
            Q(inviter=request.user) | Q(invitee=request.user),
            status="ACCEPTED",
        )

        accepted_ids = set()
        for connection in accepted_connections:
            if connection.inviter_id == request.user.id:
                accepted_ids.add(connection.invitee_id)
            else:
                accepted_ids.add(connection.inviter_id)

        unavailable_ids = PodMembership.objects.filter(
            pod=pod,
            status__in=["ACTIVE", "INVITED"],
        ).values_list("user_id", flat=True)

        users = (
            User.objects.filter(id__in=accepted_ids)
            .filter(filters)
            .exclude(id=request.user.id)
            .exclude(id__in=unavailable_ids)
            .order_by("username")[:10]
        )

        return Response(
            PodInviteCandidateSerializer(
                users,
                many=True,
                context={"request": request},
            ).data
        )