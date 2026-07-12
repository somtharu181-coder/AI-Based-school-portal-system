from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ("created_at", "event", "user", "ip_address", "model_name", "object_repr", "success")
    list_filter   = ("event", "success", "model_name")
    search_fields = ("user__username", "detail", "object_repr", "ip_address")
    readonly_fields = ("user", "event", "detail", "model_name", "object_id",
                       "object_repr", "ip_address", "user_agent", "success", "created_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False  # Audit logs must never be manually created via admin

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs are immutable

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # only superuser can purge old logs
