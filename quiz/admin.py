from django.contrib import admin
from .models import QuizSession, Question

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    readonly_fields = ("text","correct","chosen","is_correct","chapter")

@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ("student","subject","class_obj","score","total","completed","started_at")
    list_filter  = ("completed",)
    inlines      = [QuestionInline]
