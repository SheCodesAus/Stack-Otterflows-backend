from django.utils import timezone
from .models import Notification


def create_notification(*, recipient, notif_type, actor=None, payload=None):
    if recipient is None:
        return None

    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notif_type=notif_type,
        payload_json=payload or {},
    )


def create_bulk_notifications(*, recipients, notif_type, actor=None, payload=None):
    created = []
    seen_ids = set()

    for recipient in recipients:
        if recipient is None:
            continue

        recipient_id = getattr(recipient, "id", None)
        if recipient_id in seen_ids:
            continue

        seen_ids.add(recipient_id)

        created.append(
            create_notification(
                recipient=recipient,
                notif_type=notif_type,
                actor=actor,
                payload=payload,
            )
        )

    return created


def resolve_notifications(
    *,
    recipient=None,
    recipients=None,
    notif_types=None,
    payload_filters=None,
    mark_read=True,
):
    if not notif_types:
        return 0

    queryset = Notification.objects.filter(
        notif_type__in=notif_types,
        is_resolved=False,
    )

    if recipient is not None:
        queryset = queryset.filter(recipient=recipient)

    if recipients is not None:
        queryset = queryset.filter(recipient__in=recipients)

    for key, value in (payload_filters or {}).items():
        queryset = queryset.filter(**{f"payload_json__{key}": value})

    updates = {
        "is_resolved": True,
        "resolved_at": timezone.now(),
    }

    if mark_read:
        updates["is_read"] = True
        updates["read_at"] = timezone.now()

    return queryset.update(**updates)