from django.contrib import admin

from .models import AppSetting


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("admin_group_name", "invite_flow_slug", "updated_at")

    def has_add_permission(self, request):  # noqa: ARG002
        # Singleton.
        return not AppSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False
