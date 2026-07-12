import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(
                    choices=[
                        ("login_success", "Login Success"),
                        ("login_failed", "Login Failed"),
                        ("logout", "Logout"),
                        ("password_reset", "Password Reset"),
                        ("password_change", "Password Change"),
                        ("permission_denied", "Permission Denied"),
                        ("record_created", "Record Created"),
                        ("record_updated", "Record Updated"),
                        ("record_deleted", "Record Deleted"),
                        ("bulk_action", "Bulk Action"),
                        ("result_rebuilt", "Result Rebuilt"),
                        ("pdf_generated", "PDF Generated"),
                    ],
                    db_index=True,
                    max_length=50,
                )),
                ("detail", models.TextField(blank=True)),
                ("model_name", models.CharField(blank=True, max_length=100)),
                ("object_id", models.CharField(blank=True, max_length=100)),
                ("object_repr", models.CharField(blank=True, max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("success", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(
                    blank=True,
                    db_index=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="audit_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Audit Log",
                "verbose_name_plural": "Audit Logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["event", "created_at"], name="audit_event_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user", "created_at"], name="audit_user_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["model_name", "object_id"], name="audit_obj_idx"),
        ),
    ]
