from django.contrib import admin
from .models import Notification, NotificationRecipient


class RecipientInline(admin.TabularInline):
    model = NotificationRecipient
    extra = 0
    readonly_fields = ("user", "is_read", "read_at", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ("title", "category", "priority", "sender", "created_at", "is_active")
    list_filter   = ("category", "priority", "is_active")
    search_fields = ("title", "body", "sender__username")
    inlines       = [RecipientInline]


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display  = ("user", "notification", "is_read", "read_at")
    list_filter   = ("is_read",)
    search_fields = ("user__username", "notification__title")
