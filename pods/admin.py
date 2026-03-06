from django.contrib import admin

from .models import Pod, PodMembership, PodGoal, PodCheckIn

admin.site.register(Pod)
admin.site.register(PodMembership)
admin.site.register(PodGoal)
admin.site.register(PodCheckIn)

# Register your models here.
