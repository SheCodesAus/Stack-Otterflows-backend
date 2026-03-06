from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Pod, PodMembership, PodGoal, PodCheckIn
from .serializers import (
    PodSerializer,
    PodMembershipSerializer,
    PodGoalSerializer,
    PodCheckInSerializer,
)
from .permissions import is_active_member

from .models import Connection
from .serializers import ConnectionSerializer

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

    POST /api/pod-memberships/
         -> invite/add a member by user id
            body: {"pod": <pod_id>, "user": <user_id>}
            creates membership with status INVITED by default
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

        memberships = PodMembership.objects.filter(pod=pod).order_by("-created_at")
        return Response(PodMembershipSerializer(memberships, many=True).data)

    def post(self, request):
        serializer = PodMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod = serializer.validated_data["pod"]

        if not is_active_member(request.user, pod):
            return Response(
                {"detail": "Only ACTIVE members can invite others."},
                status=status.HTTP_403_FORBIDDEN,
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