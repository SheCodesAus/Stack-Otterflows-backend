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

class GoalAssignmentDetailSerializer(serializers.ModelSerializer):
    buddy_username = serializers.CharField(source="buddy.username", read_only=True)
    buddy_display_name = serializers.CharField(source="buddy.display_name", read_only=True)

    class Meta:
        model = GoalAssignment
        fields = [
            "id",
            "goal",
            "buddy",
            "buddy_username",
            "buddy_display_name",
            "consent_status",
            "created_at",
            "responded_at",
        ]
        read_only_fields = fields

class CheckInDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    created_by_display_name = serializers.CharField(source="created_by.display_name", read_only=True)
    verified_by_username = serializers.CharField(source="verified_by.username", read_only=True)
    verified_by_display_name = serializers.CharField(source="verified_by.display_name", read_only=True)

    class Meta:
        model = CheckIn
        fields = [
            "id",
            "goal",
            "created_by",
            "created_by_username",
            "created_by_display_name",
            "period_start",
            "value",
            "note",
            "proof",
            "status",
            "verified_by",
            "verified_by_username",
            "verified_by_display_name",
            "verified_at",
            "rejection_reason",
            "created_at",
        ]
        read_only_fields = fields


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

class CommentDetailSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    author_display_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "goal",
            "checkin",
            "author",
            "author_username",
            "author_display_name",
            "kind",
            "body",
            "created_at",
        ]
        read_only_fields = fields

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

class GoalDetailSerializer(serializers.ModelSerializer):
    assignments = GoalAssignmentDetailSerializer(many=True, read_only=True)
    checkins = CheckInDetailSerializer(many=True, read_only=True)
    comments = CommentDetailSerializer(many=True, read_only=True)

    latest_checkin_status = serializers.SerializerMethodField()
    latest_checkin_id = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    owner_display_name = serializers.CharField(source="owner.display_name", read_only=True)

    class Meta:
        model = Goal
        fields = [
            "id",
            "owner",
            "owner_username",
            "owner_display_name",
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
            "assignments",
            "checkins",
            "comments",
            "latest_checkin_status",
            "latest_checkin_id",
        ]
        read_only_fields = fields

    def get_latest_checkin_status(self, obj):
        latest = obj.checkins.order_by("-period_start", "-created_at").first()
        return latest.status if latest else None

    def get_latest_checkin_id(self, obj):
        latest = obj.checkins.order_by("-period_start", "-created_at").first()
        return latest.id if latest else None