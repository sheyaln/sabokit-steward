from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "target", "actor_username", "note")
    list_filter = ("action",)
    search_fields = ("target", "actor_username", "note")
    readonly_fields = (
        "actor",
        "actor_username",
        "action",
        "target",
        "before",
        "after",
        "note",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):  # noqa: ARG002
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False
