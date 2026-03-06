
# Create your models here.
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
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

    def accept(self):
        self.status = "ACCEPTED"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def decline(self):
        self.status = "DECLINED"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])


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
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title}"


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


# ------------------------------------------------------------
# FEATURE AREA 8: Notifications + nudges (in-app)
# ------------------------------------------------------------

NOTIF_TYPE = [
    ("CONNECTION_INVITE", "Connection invite"),
    ("CONNECTION_ACCEPTED", "Connection accepted"),

    ("GOAL_ASSIGNMENT_REQUEST", "Goal assignment request"),
    ("GOAL_ASSIGNMENT_ACCEPTED", "Goal assignment accepted"),

    ("CHECKIN_SUBMITTED", "Check-in submitted"),
    ("CHECKIN_APPROVED", "Check-in approved"),
    ("CHECKIN_REJECTED", "Check-in rejected"),

    # Pod-related notifications (still uses one Notification table)
    ("POD_INVITE", "Pod invite"),
    ("POD_MEMBER_JOINED", "Pod member joined"),
    ("POD_GOAL_CREATED", "Pod goal created"),
    ("POD_CHECKIN_SUBMITTED", "Pod check-in submitted"),
    ("POD_CHECKIN_APPROVED", "Pod check-in approved"),
    ("POD_CHECKIN_REJECTED", "Pod check-in rejected"),

    ("MILESTONE", "Milestone reached"),
    ("NUDGE_BEHIND", "Nudge behind"),
]


class Notification(models.Model):
    """
    In-app notification inbox. Read/unread supported.

    payload_json holds IDs/context for frontend routing.
    Example payloads:
      - {"goal_id": 1, "checkin_id": 22}
      - {"pod_id": 3, "membership_id": 44}
      - {"pod_goal_id": 8, "pod_checkin_id": 55}
    """
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPE)

    payload_json = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]


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

    def __str__(self):
        return f"{self.user} in {self.pod} ({self.status})"

    def accept(self):
        self.status = "ACTIVE"
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])


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
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pod_goals_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["pod", "is_active", "created_at"]),
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