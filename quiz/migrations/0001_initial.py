from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("academics", "0002_classroutine_room_subject_description_and_more"),
        ("students", "0003_alter_studentprofile_student_id"),
    ]
    operations = [
        migrations.CreateModel(
            name="QuizSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("score", models.IntegerField(default=0)),
                ("total", models.IntegerField(default=0)),
                ("completed", models.BooleanField(default=False)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(null=True, blank=True)),
                ("class_obj", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.class")),
                ("subject", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.subject")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quiz_sessions", to="students.studentprofile")),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("text", models.TextField()),
                ("option_a", models.CharField(max_length=300)),
                ("option_b", models.CharField(max_length=300)),
                ("option_c", models.CharField(max_length=300)),
                ("option_d", models.CharField(max_length=300)),
                ("correct", models.CharField(choices=[("A","A"),("B","B"),("C","C"),("D","D")], max_length=1)),
                ("chosen", models.CharField(blank=True, max_length=1)),
                ("is_correct", models.BooleanField(null=True)),
                ("chapter", models.CharField(blank=True, max_length=100)),
                ("order", models.PositiveIntegerField(default=0)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="quiz.quizsession")),
            ],
            options={"ordering": ["order"]},
        ),
    ]
