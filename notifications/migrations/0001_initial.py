from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("academics", "0002_classroutine_room_subject_description_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)),
                ("category", models.CharField(choices=[("internal","Internal (Staff)"),("parent","Parent"),("management","Management")], db_index=True, max_length=20)),
                ("priority", models.CharField(choices=[("low","Low"),("medium","Medium"),("high","High"),("urgent","Urgent")], default="medium", max_length=10)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sender", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_notifications", to=settings.AUTH_USER_MODEL)),
                ("target_class", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.class")),
                ("target_section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.section")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="NotificationRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipients", to="notifications.notification")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("notification", "user")}},
        ),
    ]
