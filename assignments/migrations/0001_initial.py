from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("academics", "0002_classroutine_room_subject_description_and_more"),
        ("students", "0003_alter_studentprofile_student_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Assignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("due_date", models.DateField()),
                ("max_marks", models.PositiveIntegerField(default=10)),
                ("status", models.CharField(choices=[("draft","Draft"),("published","Published"),("closed","Closed")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("class_subject", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="academics.classsubject")),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="academics.section")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="given_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Submission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("answer", models.TextField(blank=True)),
                ("marks", models.DecimalField(decimal_places=2, max_digits=5, null=True, blank=True)),
                ("grade", models.CharField(choices=[("excellent","Excellent"),("good","Good"),("average","Average"),("poor","Poor"),("pending","Pending")], default="pending", max_length=20)),
                ("feedback", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("checked_at", models.DateTimeField(null=True, blank=True)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="assignments.assignment")),
                ("checked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="checked_submissions", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="students.studentprofile")),
            ],
            options={"ordering": ["-submitted_at"], "unique_together": {("assignment", "student")}},
        ),
    ]
