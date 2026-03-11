from django.contrib import admin

from .models import Pod, PodMembership, PodGoal, PodCheckIn, Notification

admin.site.register(Pod)
admin.site.register(PodMembership)
admin.site.register(PodGoal)
admin.site.register(PodCheckIn)

# Register your models here.
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "actor",
        "notif_type",
        "is_read",
        "is_resolved",
        "created_at",
    )
    list_filter = ("notif_type", "is_read", "is_resolved", "created_at")
    search_fields = ("recipient__username", "actor__username")