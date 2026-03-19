from rest_framework.permissions import BasePermission
from .models import PodMembership, PodCheckIn, PodGoal, Pod, GoalAssignment, Goal, CheckIn

def is_active_member(user, pod: Pod) -> bool:
    """
    True if the user is an ACTIVE member of the pod.
    """
    return PodMembership.objects.filter(pod=pod, user=user, status="ACTIVE").exists()

def can_verify_checkin(user, checkin: PodCheckIn) -> bool:
    """
    True if:
    - user is an ACTIVE member of the checkin's pod, AND
    - user is NOT the person who created the checkin (no self-verify)
    """
    return is_active_member(user, checkin.pod_goal.pod) and checkin.created_by_id != user.id

def is_goal_owner(user, goal: Goal) -> bool:
    return goal.owner_id == user.id

def is_accepted_goal_buddy(user, goal: Goal) -> bool:
    return GoalAssignment.objects.filter(
        goal=goal,
        buddy=user,
        consent_status="ACCEPTED",
    ).exists()

def can_view_goal(user, goal: Goal) -> bool:
    return is_goal_owner(user, goal) or is_accepted_goal_buddy(user, goal)

def can_verify_individual_checkin(user, checkin: CheckIn) -> bool:
    return (
        checkin.created_by_id != user.id
        and is_accepted_goal_buddy(user, checkin.goal)
    )

class IsActivePodMember(BasePermission):
    """
    Object-level permission.
    Allows access only if the request.user is an ACTIVE member of the relevant pod.

    Works with:
    - Pod objects
    - PodGoal objects (via obj.pod)
    - PodCheckIn objects (via obj.pod_goal.pod)
    """
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Pod):
            pod = obj
        elif isinstance(obj, PodGoal):
            pod = obj.pod
        elif isinstance(obj, PodCheckIn):
            pod = obj.pod_goal.pod
        else:
            return False

        return is_active_member(request.user, pod)


class CanVerifyPodCheckIn(BasePermission):
    """
    Object-level permission for approve/reject actions.
    The user must be an ACTIVE pod member and cannot verify their own check-in.
    """
    def has_object_permission(self, request, view, obj):
        if not isinstance(obj, PodCheckIn):
            return False
        return can_verify_checkin(request.user, obj)