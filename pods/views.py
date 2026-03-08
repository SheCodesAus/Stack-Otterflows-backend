from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import (
Pod, PodMembership, PodGoal, PodCheckIn, Connection,
Goal, GoalAssignment, CheckIn, Comment, PodComment)

from .serializers import (
    PodSerializer,
    PodMembershipSerializer,
    PodGoalSerializer,
    PodCheckInSerializer,
    ConnectionSerializer,
    GoalSerializer, GoalAssignmentSerializer, CheckInSerializer, CommentSerializer, PodCommentSerializer,
)
from .permissions import ( 
    is_active_member,
    is_goal_owner,
    is_accepted_goal_buddy,
    can_view_goal,
    can_verify_individual_checkin, )


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
    GET /api/goals/<goal_id>/ -> retrieve one goal
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id)

        if not can_view_goal(request.user, goal):
            return Response(
                {"detail": "You do not have permission to view this goal."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(GoalSerializer(goal).data)


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

        return Response(
            GoalAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class GoalAssignmentAcceptView(APIView):
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
        return Response({"detail": "Assignment accepted."})


class GoalAssignmentDeclineView(APIView):
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
        return Response({"detail": "Assignment declined."})

class PodListCreateView(APIView):
    """
    GET  /api/pods/        -> list pods where I am ACTIVE member
    POST /api/pods/        -> create a pod and auto-create OWNER membership for me
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pods = Pod.objects.filter(
            memberships__user=request.user,
            memberships__status="ACTIVE",
        ).distinct()
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

        return Response(PodSerializer(pod).data, status=status.HTTP_201_CREATED)


class PodDetailView(APIView):
    """
    GET /api/pods/<pod_id>/ -> retrieve pod (must be ACTIVE member)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pod_id):
        pod = get_object_or_404(Pod, id=pod_id)

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "You are not an ACTIVE member of this pod."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(PodSerializer(pod).data)


class PodMembershipListCreateView(APIView):
    """
    GET  /api/pod-memberships/?pod=<pod_id>
         -> list memberships for a pod (must be ACTIVE member)

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
            return Response(PodMembershipSerializer(memberships, many=True).data)

        memberships = PodMembership.objects.filter(user=request.user).order_by("-created_at")
        return Response(PodMembershipSerializer(memberships, many=True).data)

    def post(self, request):
        serializer = PodMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod = serializer.validated_data["pod"]
        invited_user = serializer.validated_data["user"]

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

        try:
            membership = serializer.save(
                invited_by=request.user,
                status="INVITED",
                role="MEMBER",
            )
        except IntegrityError:
            return Response(
                {"detail": "That user already has a membership for this pod."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PodMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class PodMembershipAcceptView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/accept/
    Only the invited user can accept their invite.
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
        return Response({"detail": "Membership accepted."})


class PodMembershipDeclineView(APIView):
    """
    POST /api/pod-memberships/<membership_id>/decline/
    Only the invited user can decline their invite.
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
        return Response({"detail": "Membership declined."})


class PodGoalListCreateView(APIView):
    """
    GET  /api/pod-goals/?pod=<pod_id> -> list goals in pod (must be ACTIVE member)
    POST /api/pod-goals/              -> create pod goal (must be ACTIVE member)
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
        return Response(PodGoalSerializer(goal).data, status=status.HTTP_201_CREATED)


class PodCheckInListCreateView(APIView):
    """
    GET  /api/pod-checkins/?pod_goal=<pod_goal_id> -> list check-ins for a goal (ACTIVE member only)
    POST /api/pod-checkins/                        -> create check-in (ACTIVE member only)
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
        return Response(
            PodCheckInSerializer(checkin).data,
            status=status.HTTP_201_CREATED,
        )
    
class CheckInListCreateView(APIView):
    """
    GET  /api/checkins/?goal=<goal_id>
    POST /api/checkins/
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
        return Response(CheckInSerializer(checkin).data, status=status.HTTP_201_CREATED)


class CheckInApproveView(APIView):
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
        return Response({"detail": "Approved."})


class CheckInRejectView(APIView):
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
        return Response({"detail": "Rejected.", "reason": reason})

class PodCheckInApproveView(APIView):
    """
    POST /api/pod-checkins/<checkin_id>/approve/

    Rules:
    - verifier must be ACTIVE member
    - verifier cannot approve their own check-in
    - only PENDING check-ins can be approved
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
        return Response({"detail": "Approved."})


class PodCheckInRejectView(APIView):
    """
    POST /api/pod-checkins/<checkin_id>/reject/
    Body: {"reason": "short reason"}

    Rules:
    - verifier must be ACTIVE member
    - verifier cannot reject their own check-in
    - only PENDING check-ins can be rejected
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
        return Response({"detail": "Rejected.", "reason": reason})
    
class ConnectionListCreateView(APIView):
    """
    GET  /api/connections/ -> list my connection records
    POST /api/connections/ -> create a connection invite

    POST body:
    {
      "invitee": <user_id>
    }
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

        try:
            connection = Connection.objects.create(
                inviter=request.user,
                invitee=invitee,
                status="PENDING",
            )
        except IntegrityError:
            return Response(
                {"detail": "A connection between these users already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ConnectionSerializer(connection).data,
            status=status.HTTP_201_CREATED,
        )


class ConnectionAcceptView(APIView):
    """
    POST /api/connections/<connection_id>/accept/
    Only the invitee can accept.
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
        return Response({"detail": "Connection accepted."})


class ConnectionDeclineView(APIView):
    """
    POST /api/connections/<connection_id>/decline/
    Only the invitee can decline.
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
        return Response({"detail": "Connection declined."})
    

class CommentListCreateView(APIView):
    """
    GET  /api/comments/?goal=<goal_id>
    POST /api/comments/

    POST body:
    {
      "goal": <goal_id>,
      "checkin": <optional_checkin_id>,
      "kind": "COMMENT",
      "body": "Nice work"
    }
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
    
class PodCommentListCreateView(APIView):
    """
    GET  /api/pod-comments/?pod_goal=<pod_goal_id>
    POST /api/pod-comments/

    POST body:
    {
      "pod_goal": <pod_goal_id>,
      "checkin": <optional_pod_checkin_id>,
      "kind": "COMMENT",
      "body": "Great progress"
    }
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