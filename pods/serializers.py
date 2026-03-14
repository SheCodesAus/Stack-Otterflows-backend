from django.contrib.auth import get_user_model

User = get_user_model()

from rest_framework import serializers
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
    Notification
)


# ------------------------------------------------------------
# GOALS
# ------------------------------------------------------------

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
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

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

    def validate(self, attrs):
        if self.instance and "goal" in attrs and attrs["goal"].id != self.instance.goal_id:
            raise serializers.ValidationError("You cannot change the goal of an existing check-in.")
        return attrs


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

    def validate(self, attrs):
        goal = attrs.get("goal", getattr(self.instance, "goal", None))
        checkin = attrs.get("checkin", getattr(self.instance, "checkin", None))

        if checkin and goal and checkin.goal_id != goal.id:
            raise serializers.ValidationError("That check-in does not belong to this goal.")

        return attrs


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
            "status",
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


# ------------------------------------------------------------
# PODS
# ------------------------------------------------------------

class PodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pod
        fields = ["id", "name", "description", "created_by", "created_at", "is_active"]
        read_only_fields = ["id", "created_by", "created_at"]


class PodMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodMembership
        fields = [
            "id",
            "pod",
            "user",
            "role",
            "status",
            "invited_by",
            "created_at",
            "responded_at",
        ]
        read_only_fields = ["id", "role", "status", "invited_by", "created_at", "responded_at"]


class PodMembershipDetailSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_display_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = PodMembership
        fields = [
            "id",
            "pod",
            "user",
            "user_username",
            "user_display_name",
            "role",
            "status",
            "invited_by",
            "created_at",
            "responded_at",
        ]
        read_only_fields = fields


class PodGoalSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    created_by_display_name = serializers.CharField(source="created_by.display_name", read_only=True)

    class Meta:
        model = PodGoal
        fields = [
            "id",
            "pod",
            "title",
            "motivation",
            "category",
            "metric_type",
            "period",
            "target_value",
            "unit_label",
            "start_date",
            "end_date",
            "status",
            "created_by",
            "created_by_username",
            "created_by_display_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError("end_date cannot be before start_date.")

        return attrs


class PodCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = PodCheckIn
        fields = [
            "id",
            "pod_goal",
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

    def validate(self, attrs):
        if self.instance and "pod_goal" in attrs and attrs["pod_goal"].id != self.instance.pod_goal_id:
            raise serializers.ValidationError("You cannot change the pod goal of an existing check-in.")
        return attrs


class PodCheckInDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    created_by_display_name = serializers.CharField(source="created_by.display_name", read_only=True)
    verified_by_username = serializers.CharField(source="verified_by.username", read_only=True)
    verified_by_display_name = serializers.CharField(source="verified_by.display_name", read_only=True)

    class Meta:
        model = PodCheckIn
        fields = [
            "id",
            "pod_goal",
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

    def validate(self, attrs):
        pod_goal = attrs.get("pod_goal", getattr(self.instance, "pod_goal", None))
        checkin = attrs.get("checkin", getattr(self.instance, "checkin", None))

        if checkin and pod_goal and checkin.pod_goal_id != pod_goal.id:
            raise serializers.ValidationError("That pod check-in does not belong to this pod goal.")

        return attrs


class PodCommentDetailSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    author_display_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = PodComment
        fields = [
            "id",
            "pod_goal",
            "checkin",
            "author",
            "author_username",
            "author_display_name",
            "kind",
            "body",
            "created_at",
        ]
        read_only_fields = fields


class PodDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    created_by_display_name = serializers.CharField(source="created_by.display_name", read_only=True)
    memberships = PodMembershipDetailSerializer(many=True, read_only=True)
    pod_goals = PodGoalSerializer(source="goals", many=True, read_only=True)
    pod_checkins = serializers.SerializerMethodField()
    pod_comments = serializers.SerializerMethodField()

    class Meta:
        model = Pod
        fields = [
            "id",
            "name",
            "description",
            "created_by",
            "created_by_username",
            "created_by_display_name",
            "created_at",
            "is_active",
            "memberships",
            "pod_goals",
            "pod_checkins",
            "pod_comments",
        ]
        read_only_fields = fields

    def get_pod_checkins(self, obj):
        checkins = PodCheckIn.objects.filter(
            pod_goal__pod=obj
        ).order_by("-period_start", "-created_at")
        return PodCheckInDetailSerializer(checkins, many=True).data

    def get_pod_comments(self, obj):
        comments = PodComment.objects.filter(
            pod_goal__pod=obj
        ).order_by("-created_at")
        return PodCommentDetailSerializer(comments, many=True).data


# ------------------------------------------------------------
# CONNECTIONS
# ------------------------------------------------------------

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
# ------------------------------------------------------------
# NOTIFICATIONS
# ------------------------------------------------------------

class NotificationSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_notif_type_display", read_only=True)
    actor_name = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()
    is_needs_review = serializers.SerializerMethodField()
    is_action_required = serializers.SerializerMethodField()
    assignment_id = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "notif_type",
            "type_label",
            "actor_name",
            "title",
            "message",
            "target_url",
            "payload_json",
            "assignment_id",
            "is_read",
            "read_at",
            "is_resolved",
            "resolved_at",
            "is_needs_review",
            "is_action_required",
            "created_at",
        ]

    def get_actor_name(self, obj):
        return obj.get_actor_name()

    def get_title(self, obj):
        return obj.get_title()

    def get_message(self, obj):
        return obj.get_message()

    def get_target_url(self, obj):
        return obj.get_target_url()

    def get_is_needs_review(self, obj):
        return obj.is_needs_review

    def get_is_action_required(self, obj):
        return obj.is_action_required

    def get_assignment_id(self, obj):
        return (obj.payload_json or {}).get("assignment_id")


class UserSearchSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "display_name"]
        read_only_fields = fields

    def get_display_name(self, obj):
        return (
            getattr(obj, "display_name", None)
            or obj.get_full_name().strip()
            or obj.username
        )