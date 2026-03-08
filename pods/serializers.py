from rest_framework import serializers
from .models import ( 
Pod, PodMembership, PodGoal, PodCheckIn, Connection,
Goal, GoalAssignment, CheckIn, Comment, PodComment )

class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = [
            "id",
            "owner",
            "title",
            "motivation",
            "category",
            "metric_type",
            "period",
            "target_value",
            "unit_label",
            "start_date",
            "end_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError("end_date cannot be before start_date.")

        return attrs


class GoalAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalAssignment
        fields = [
            "id",
            "goal",
            "buddy",
            "consent_status",
            "created_at",
            "responded_at",
        ]
        read_only_fields = ["id", "consent_status", "created_at", "responded_at"]


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = [
            "id",
            "goal",
            "created_by",
            "period_start",
            "value",
            "note",
            "proof",
            "status",
            "verified_by",
            "verified_at",
            "rejection_reason",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "status",
            "verified_by",
            "verified_at",
            "rejection_reason",
            "created_at",
        ]


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = [
            "id",
            "goal",
            "checkin",
            "author",
            "kind",
            "body",
            "created_at",
        ]
        read_only_fields = ["id", "author", "created_at"]

class PodCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodComment
        fields = [
            "id",
            "pod_goal",
            "checkin",
            "author",
            "kind",
            "body",
            "created_at",
        ]
        read_only_fields = ["id", "author", "created_at"]

class PodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pod
        fields = ["id", "name", "description", "created_by", "created_at", "is_active"]
        read_only_fields = ["id", "created_by", "created_at"]

class PodMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodMembership
        fields = ["id", "pod", "user", "role", "status", "invited_by", "created_at", "responded_at"]
        read_only_fields = ["id", "role", "status", "invited_by", "created_at", "responded_at"]

class PodGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodGoal
        fields = [
            "id", "pod", "title", "motivation", "category",
            "metric_type", "period", "target_value", "unit_label",
            "start_date", "end_date", "is_active",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

class PodCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodCheckIn
        fields = [
            "id", "pod_goal", "created_by", "period_start", "value",
            "note", "proof", "status", "verified_by", "verified_at",
            "rejection_reason", "created_at",
        ]
        read_only_fields = ["id", "created_by", "status", "verified_by", "verified_at", "created_at"]

class ConnectionSerializer(serializers.ModelSerializer):
    inviter_username = serializers.CharField(source="inviter.username", read_only=True)
    inviter_display_name = serializers.CharField(source="inviter.display_name", read_only=True)
    invitee_username = serializers.CharField(source="invitee.username", read_only=True)
    invitee_display_name = serializers.CharField(source="invitee.display_name", read_only=True)

    class Meta:
        model = Connection
        fields = [
            "id",
            "inviter",
            "invitee",
            "status",
            "created_at",
            "responded_at",
            "inviter_username",
            "inviter_display_name",
            "invitee_username",
            "invitee_display_name",
        ]
        read_only_fields = [
            "id",
            "inviter",
            "status",
            "created_at",
            "responded_at",
            "inviter_username",
            "inviter_display_name",
            "invitee_username",
            "invitee_display_name",
        ]