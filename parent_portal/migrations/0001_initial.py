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
            name="ParentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("phone", models.CharField(blank=True, max_length=15)),
                ("address", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="parent_profile", to=settings.AUTH_USER_MODEL)),
                ("children", models.ManyToManyField(blank=True, related_name="parents", to="students.studentprofile")),
            ],
        ),
        migrations.CreateModel(
            name="OnlineMeeting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("meeting_url", models.URLField(blank=True)),
                ("scheduled_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("scheduled","Scheduled"),("live","Live"),("ended","Ended"),("cancelled","Cancelled")], default="scheduled", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("host", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="hosted_meetings", to=settings.AUTH_USER_MODEL)),
                ("target_class", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.class")),
            ],
            options={"ordering": ["-scheduled_at"]},
        ),
        migrations.CreateModel(
            name="SchoolLetter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField()),
                ("is_published", models.BooleanField(default=False)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("issued_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_letters", to=settings.AUTH_USER_MODEL)),
                ("target_class", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.class")),
            ],
            options={"ordering": ["-issued_at"]},
        ),
    ]
