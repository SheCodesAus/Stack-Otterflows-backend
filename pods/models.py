from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

User = settings.AUTH_USER_MODEL

# ------------------------------------------------------------
# FEATURE AREA 2: Connections (Invite-only)
# ------------------------------------------------------------

CONNECTION_STATUS = [
    ("PENDING", "Pending"),
    ("ACCEPTED", "Accepted"),
    ("DECLINED", "Declined"),
    ("BLOCKED", "Blocked"),
]


class Connection(models.Model):
    """
    Represents an invite-only relationship between two users.
    This supports:
    - user A invites user B
    - user B accepts/declines
    Privacy: no public search required.
    """
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_connections")
    invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_connections")
    status = models.CharField(max_length=10, choices=CONNECTION_STATUS, default="PENDING")

    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("inviter", "invitee")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(inviter=F("invitee")),
                name="connection_no_self_invite",
        ),
    ]

    def clean(self):
        if self.inviter_id and self.invitee_id:
            existing = Connection.objects.filter(
                Q(inviter_id=self.inviter_id, invitee_id=self.invitee_id) |
                Q(inviter_id=self.invitee_id, invitee_id=self.inviter_id)
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)

            if existing.exists():
                raise ValidationError("A connection between these users already exists.")

    def accept(self):
        self.status = "ACCEPTED"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def decline(self):
        self.status = "DECLINED"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def __str__(self):
        return f"{self.inviter} -> {self.invitee} ({self.status})"


# ------------------------------------------------------------
# FEATURE AREA 3: Goals (Metric types + Category choices)
# ------------------------------------------------------------

METRIC_TYPE = [
    ("BINARY", "Binary"),
    ("COUNT", "Count"),
    ("DURATION", "Duration"),
]

PERIOD_TYPE = [
    ("DAILY", "Daily"),
    ("WEEKLY", "Weekly"),
]

GOAL_CATEGORY = [
    ("HEALTH", "Health"),
    ("EDUCATION", "Education"),
    ("FITNESS", "Fitness"),
    ("CAREER", "Career"),
    ("CREATIVE", "Creative"),
    ("WELLBEING", "Wellbeing"),
    ("OTHER", "Other"),
]

GOAL_STATUS = [
    ("PLANNED", "Planned"),
    ("ACTIVE", "Active"),
    ("PAUSED", "Paused"),
    ("COMPLETED", "Completed"),
    ("ARCHIVED", "Archived"),
]


class Goal(models.Model):
    """
    A structured goal owned by a user. Metric type controls how check-ins work.
    """
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="goals")
    title = models.CharField(max_length=120)
    motivation = models.TextField(blank=True)

    category = models.CharField(max_length=20, choices=GOAL_CATEGORY, default="OTHER")
    metric_type = models.CharField(max_length=10, choices=METRIC_TYPE)
    period = models.CharField(max_length=10, choices=PERIOD_TYPE)

    target_value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_label = models.CharField(max_length=20, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=GOAL_STATUS, default="ACTIVE")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


# ------------------------------------------------------------
# FEATURE AREA 4: Accountability assignment + consent (Individual)
# ------------------------------------------------------------

CONSENT_STATUS = [
    ("PENDING", "Pending"),
    ("ACCEPTED", "Accepted"),
    ("DECLINED", "Declined"),
]


class GoalAssignment(models.Model):
    """
    Who can verify for this goal.
    Consent must be accepted before verification rights apply.
    """
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="assignments")
    buddy = models.ForeignKey(User, on_delete=models.CASCADE, related_name="goal_assignments")
    consent_status = models.CharField(max_length=10, choices=CONSENT_STATUS, default="PENDING")

    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("goal", "buddy")]

    def accept(self):
        self.consent_status = "ACCEPTED"
        self.responded_at = timezone.now()
        self.save(update_fields=["consent_status", "responded_at"])

    def decline(self):
        self.consent_status = "DECLINED"
        self.responded_at = timezone.now()
        self.save(update_fields=["consent_status", "responded_at"])

    def __str__(self):
        return f"{self.buddy} assigned to {self.goal} ({self.consent_status})"


# ------------------------------------------------------------
# FEATURE AREA 5: Check-ins + proof + verification (Individual)
# ------------------------------------------------------------

CHECKIN_STATUS = [
    ("PENDING", "Pending"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
]


class CheckIn(models.Model):
    """
    A log entry against a goal for a specific period.
    - period_start buckets check-ins for daily/weekly calculations.
    - value is unified:
        - BINARY: 1
        - COUNT: numeric units
        - DURATION: minutes
    """
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="checkins")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="checkins_created")

    period_start = models.DateField()
    value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.TextField(blank=True)

    proof = models.FileField(upload_to="proofs/", null=True, blank=True)

    status = models.CharField(max_length=10, choices=CHECKIN_STATUS, default="PENDING")

    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="checkins_verified"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["goal", "period_start", "status"]),
            models.Index(fields=["created_by", "created_at"]),
        ]

    def approve(self, verifier):
        self.status = "APPROVED"
        self.verified_by = verifier
        self.verified_at = timezone.now()
        self.rejection_reason = ""
        self.save(update_fields=["status", "verified_by", "verified_at", "rejection_reason"])

    def reject(self, verifier, reason=""):
        self.status = "REJECTED"
        self.verified_by = verifier
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=["status", "verified_by", "verified_at", "rejection_reason"])

    def __str__(self):
        return f"{self.goal} - {self.created_by} ({self.status})"


# ------------------------------------------------------------
# FEATURE AREA 6: Comments + encouragement (Individual)
# ------------------------------------------------------------

COMMENT_KIND = [
    ("COMMENT", "Comment"),
    ("KUDOS", "Kudos"),
    ("CLARIFY", "Clarify"),
]


class Comment(models.Model):
    """
    Private comments within a goal space.
    Optional: attach to a specific check-in for clarification threads.
    """
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="comments")
    checkin = models.ForeignKey(CheckIn, on_delete=models.CASCADE, null=True, blank=True, related_name="comments")

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments_written")
    kind = models.CharField(max_length=10, choices=COMMENT_KIND, default="COMMENT")
    body = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["goal", "created_at"]),
            models.Index(fields=["author", "created_at"]),
        ]

    def clean(self):
        if self.checkin_id and self.goal_id and self.checkin.goal_id != self.goal_id:
            raise ValidationError("That check-in does not belong to this goal.")

    def __str__(self):
        return f"{self.author} on {self.goal}"


# ------------------------------------------------------------
# FEATURE AREA 8: Notifications + nudges (in-app)
# ------------------------------------------------------------

NOTIF_TYPE = [
    ("CONNECTION_INVITE", "Connection invite"),
    ("CONNECTION_ACCEPTED", "Connection accepted"),
    ("CONNECTION_DECLINED", "Connection declined"),
    ("GOAL_ASSIGNMENT_REQUEST", "Goal assignment request"),
    ("GOAL_ASSIGNMENT_ACCEPTED", "Goal assignment accepted"),
    ("GOAL_ASSIGNMENT_DECLINED", "Goal assignment declined"),
    ("CHECKIN_SUBMITTED", "Check-in submitted"),
    ("CHECKIN_APPROVED", "Check-in approved"),
    ("CHECKIN_REJECTED", "Check-in rejected"),

    # Pod-related notifications
    ("POD_INVITE", "Pod invite"),
    ("POD_INVITE_DECLINED", "Pod invite declined"),
    ("POD_MEMBER_JOINED", "Pod member joined"),
    ("POD_GOAL_CREATED", "Pod goal created"),
    ("POD_CHECKIN_SUBMITTED", "Pod check-in submitted"),
    ("POD_CHECKIN_APPROVED", "Pod check-in approved"),
    ("POD_CHECKIN_REJECTED", "Pod check-in rejected"),

    ("MILESTONE", "Milestone reached"),
    ("NUDGE_BEHIND", "Nudge behind"),
]

ACTION_REQUIRED_NOTIFICATION_TYPES = {
    "CONNECTION_INVITE",
    "GOAL_ASSIGNMENT_REQUEST",
    "CHECKIN_SUBMITTED",
    "POD_INVITE",
    "POD_CHECKIN_SUBMITTED",
}


class NotificationQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related("recipient", "actor")

    def for_user(self, user):
        return self.filter(recipient=user)

    def unread(self):
        return self.filter(is_read=False)

    def needs_review(self):
        return self.filter(
            notif_type__in=ACTION_REQUIRED_NOTIFICATION_TYPES,
            is_resolved=False,
        )


class Notification(models.Model):
    """
    In-app notification inbox.

    payload_json can hold routing/context for the frontend.
    Example payloads:
      - {"goal_id": 1, "goal_title": "Meditate", "checkin_id": 22}
      - {"pod_id": 3, "pod_name": "Morning Crew", "membership_id": 44}
      - {"pod_id": 3, "pod_goal_id": 8, "pod_checkin_id": 55}
      - {"target_url": "/goals/1"}
    """

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPE)

    payload_json = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["recipient", "is_resolved", "created_at"]),
            models.Index(fields=["recipient", "notif_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.notif_type}"

    @property
    def is_action_required(self):
        return self.notif_type in ACTION_REQUIRED_NOTIFICATION_TYPES

    @property
    def is_needs_review(self):
        return self.is_action_required and not self.is_resolved

    def get_actor_name(self):
        if self.actor:
            return (
                getattr(self.actor, "display_name", None)
                or getattr(self.actor, "username", None)
                or getattr(self.actor, "first_name", None)
                or getattr(self.actor, "email", None)
                or "Someone"
            )

        return self.payload_json.get("actor_name") or "Someone"

    def get_title(self):
        title_map = {
            "CONNECTION_INVITE": "Connection invite",
            "CONNECTION_ACCEPTED": "Connection accepted",
            "CONNECTION_DECLINED": "Connection declined",
            "GOAL_ASSIGNMENT_REQUEST": "Buddy request",
            "GOAL_ASSIGNMENT_ACCEPTED": "Buddy request accepted",
            "GOAL_ASSIGNMENT_DECLINED": "Buddy request declined",
            "CHECKIN_SUBMITTED": "Check-in needs review",
            "CHECKIN_APPROVED": "Check-in approved",
            "CHECKIN_REJECTED": "Check-in rejected",
            "POD_INVITE": "Pod invite",
            "POD_INVITE_DECLINED": "Pod invite declined",
            "POD_MEMBER_JOINED": "New pod member",
            "POD_GOAL_CREATED": "New pod goal",
            "POD_CHECKIN_SUBMITTED": "Pod check-in needs review",
            "POD_CHECKIN_APPROVED": "Pod check-in approved",
            "POD_CHECKIN_REJECTED": "Pod check-in rejected",
            "MILESTONE": "Milestone reached",
            "NUDGE_BEHIND": "Nudge behind",
        }
        return title_map.get(self.notif_type, "Notification")

    def get_message(self):
        actor_name = self.get_actor_name()
        payload = self.payload_json or {}

        goal_title = payload.get("goal_title")
        pod_name = payload.get("pod_name")

        goal_suffix = f' for "{goal_title}"' if goal_title else ""
        pod_suffix = f' in "{pod_name}"' if pod_name else ""

        if self.notif_type == "CONNECTION_INVITE":
            return f"{actor_name} sent you a connection invite."

        if self.notif_type == "CONNECTION_ACCEPTED":
            return f"{actor_name} accepted your connection invite."
        
        if self.notif_type == "CONNECTION_DECLINED":
            return f"{actor_name} declined your connection invite."

        if self.notif_type == "GOAL_ASSIGNMENT_DECLINED":
            return f"{actor_name} declined your buddy request{goal_suffix}."

        if self.notif_type == "POD_INVITE_DECLINED":
            return f"{actor_name} declined your pod invite{pod_suffix}."

        if self.notif_type == "GOAL_ASSIGNMENT_REQUEST":
            return f"{actor_name} invited you to be a buddy{goal_suffix}."

        if self.notif_type == "GOAL_ASSIGNMENT_ACCEPTED":
            return f"{actor_name} accepted your buddy request{goal_suffix}."

        if self.notif_type == "CHECKIN_SUBMITTED":
            return f"{actor_name} submitted a check-in{goal_suffix} that needs review."

        if self.notif_type == "CHECKIN_APPROVED":
            return f"{actor_name} approved your check-in{goal_suffix}."

        if self.notif_type == "CHECKIN_REJECTED":
            return f"{actor_name} rejected your check-in{goal_suffix}."

        if self.notif_type == "POD_INVITE":
            return f"{actor_name} invited you to join a pod{pod_suffix}."

        if self.notif_type == "POD_MEMBER_JOINED":
            return f"{actor_name} joined your pod{pod_suffix}."

        if self.notif_type == "POD_GOAL_CREATED":
            return f"{actor_name} created a new pod goal{pod_suffix}."

        if self.notif_type == "POD_CHECKIN_SUBMITTED":
            return f"{actor_name} submitted a pod check-in{pod_suffix} that needs review."

        if self.notif_type == "POD_CHECKIN_APPROVED":
            return f"{actor_name} approved a pod check-in{pod_suffix}."

        if self.notif_type == "POD_CHECKIN_REJECTED":
            return f"{actor_name} rejected a pod check-in{pod_suffix}."

        if self.notif_type == "MILESTONE":
            return payload.get("message") or "You reached a milestone."

        if self.notif_type == "NUDGE_BEHIND":
            return payload.get("message") or "You may be falling behind your target."

        return payload.get("message") or "You have a new notification."

    def get_target_url(self):
        payload = self.payload_json or {}

        if payload.get("target_url"):
            return payload["target_url"]

        if payload.get("goal_id"):
            return f"/goals/{payload['goal_id']}"

        if payload.get("pod_id") and payload.get("pod_goal_id"):
            return f"/pods/{payload['pod_id']}/goals/{payload['pod_goal_id']}"

        if payload.get("pod_id"):
            return f"/pods/{payload['pod_id']}"

        if self.notif_type in {"CONNECTION_INVITE", "CONNECTION_ACCEPTED", "CONNECTION_DECLINED",}:
            return "/connections"

        return "/dashboard"

    def mark_read(self, save=True):
        self.is_read = True
        self.read_at = timezone.now()
        if save:
            self.save(update_fields=["is_read", "read_at"])

    def mark_unread(self, save=True):
        self.is_read = False
        self.read_at = None
        if save:
            self.save(update_fields=["is_read", "read_at"])

    def mark_resolved(self, save=True, mark_read=False):
        self.is_resolved = True
        self.resolved_at = timezone.now()

        update_fields = ["is_resolved", "resolved_at"]

        if mark_read:
            self.is_read = True
            self.read_at = timezone.now()
            update_fields.extend(["is_read", "read_at"])

        if save:
            self.save(update_fields=update_fields)


# ------------------------------------------------------------
# POD MODEL (for groups)
# ------------------------------------------------------------

class Pod(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pods_created")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# POD MEMBERSHIP
# ------------------------------------------------------------

POD_ROLE = [
    ("OWNER", "Owner"),
    ("ADMIN", "Admin"),
    ("MEMBER", "Member"),
]

MEMBERSHIP_STATUS = [
    ("INVITED", "Invited"),
    ("ACTIVE", "Active"),
    ("DECLINED", "Declined"),
    ("LEFT", "Left"),
    ("REMOVED", "Removed"),
]


class PodMembership(models.Model):
    pod = models.ForeignKey(Pod, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pod_memberships")

    role = models.CharField(max_length=10, choices=POD_ROLE, default="MEMBER")
    status = models.CharField(max_length=10, choices=MEMBERSHIP_STATUS, default="INVITED")

    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pod_invites_sent"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("pod", "user")]
        indexes = [
            models.Index(fields=["pod", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def accept(self):
        self.status = "ACTIVE"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def decline(self):
        self.status = "DECLINED"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def __str__(self):
        return f"{self.user} in {self.pod} ({self.status})"


# ------------------------------------------------------------
# POD GOALS
# ------------------------------------------------------------

class PodGoal(models.Model):
    pod = models.ForeignKey(Pod, on_delete=models.CASCADE, related_name="goals")

    title = models.CharField(max_length=120)
    motivation = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=GOAL_CATEGORY, default="OTHER")

    metric_type = models.CharField(max_length=10, choices=METRIC_TYPE)
    period = models.CharField(max_length=10, choices=PERIOD_TYPE)

    target_value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_label = models.CharField(max_length=20, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=GOAL_STATUS, default="ACTIVE")

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pod_goals_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["pod", "status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.pod.name}: {self.title}"


# ------------------------------------------------------------
# POD CHECK-INS
# ------------------------------------------------------------

class PodCheckIn(models.Model):
    pod_goal = models.ForeignKey(PodGoal, on_delete=models.CASCADE, related_name="checkins")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pod_checkins_created")

    period_start = models.DateField()
    value = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.TextField(blank=True)
    proof = models.FileField(upload_to="proofs/", null=True, blank=True)

    status = models.CharField(max_length=10, choices=CHECKIN_STATUS, default="PENDING")

    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pod_checkins_verified"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["pod_goal", "period_start", "status"]),
            models.Index(fields=["created_by", "created_at"]),
        ]

    def approve(self, verifier):
        self.status = "APPROVED"
        self.verified_by = verifier
        self.verified_at = timezone.now()
        self.rejection_reason = ""
        self.save(update_fields=["status", "verified_by", "verified_at", "rejection_reason"])

    def reject(self, verifier, reason=""):
        self.status = "REJECTED"
        self.verified_by = verifier
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=["status", "verified_by", "verified_at", "rejection_reason"])

    def __str__(self):
        return f"{self.pod_goal} - {self.created_by} ({self.status})"

    """
    IMPORTANT RULE (enforced in API logic, not DB):
      - verifier must be an ACTIVE member of pod_goal.pod
      - verifier cannot be the same user as created_by (no self verification)
    """


# ------------------------------------------------------------
# POD COMMENTS (separate table for MVP simplicity)
# ------------------------------------------------------------

class PodComment(models.Model):
    pod_goal = models.ForeignKey(PodGoal, on_delete=models.CASCADE, related_name="comments")
    checkin = models.ForeignKey(
        PodCheckIn, on_delete=models.CASCADE, null=True, blank=True, related_name="comments"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pod_comments_written")
    kind = models.CharField(max_length=10, choices=COMMENT_KIND, default="COMMENT")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["pod_goal", "created_at"]),
            models.Index(fields=["author", "created_at"]),
        ]

    def clean(self):
        if self.checkin_id and self.pod_goal_id and self.checkin.pod_goal_id != self.pod_goal_id:
            raise ValidationError("That pod check-in does not belong to this pod goal.")

    def __str__(self):
        return f"{self.author} on {self.pod_goal}"


# ============================================================
# OPTIONAL TABLES (include only if/when you build these features)
# ============================================================

# ------------------------------------------------------------
# OPTIONAL: User preferences (frontend theme, channels)
# ------------------------------------------------------------

# THEME_CHOICES = [
#     ("DARK", "Dark"),
#     ("LIGHT", "Light"),
#     ("SYSTEM", "System"),
# ]


# class UserPreference(models.Model):
#     """
#     Optional. Useful if you want:
#     - theme preference
#     - whether the user wants email nudges
#     """
#     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")
#     theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="DARK")
#     email_notifications_enabled = models.BooleanField(default=False)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)


# ------------------------------------------------------------
# OPTIONAL: Delivery log for emails (prevents duplicates)
# ------------------------------------------------------------

# DELIVERY_CHANNEL = [
#     ("IN_APP", "In-app"),
#     ("EMAIL", "Email"),
# ]

# DELIVERY_STATUS = [
#     ("SENT", "Sent"),
#     ("FAILED", "Failed"),
# ]


# class NotificationDelivery(models.Model):
#     """
#     Optional. Tracks delivery attempts, mostly useful for email.
#     If you do not build email in MVP, you can skip this table.
#     """
#     notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
#     channel = models.CharField(max_length=10, choices=DELIVERY_CHANNEL)
#     status = models.CharField(max_length=10, choices=DELIVERY_STATUS)

#     detail = models.TextField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)