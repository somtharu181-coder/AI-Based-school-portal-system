from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import QuizSession, Question
from .services import start_quiz_session, submit_answer, finish_session
from academics.models import Subject


@login_required
def home(request):
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect("accounts:student_dashboard")
    sessions  = QuizSession.objects.filter(student=sp).order_by("-started_at")[:10]
    subjects  = Subject.objects.all().order_by("name")
    return render(request, "quiz/home.html", {"sessions": sessions, "subjects": subjects, "sp": sp})


@login_required
def start(request):
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect("accounts:student_dashboard")
    subject_id = request.POST.get("subject_id")
    subject    = Subject.objects.filter(pk=subject_id).first() if subject_id else None
    session    = start_quiz_session(sp, subject)
    return redirect("quiz:attempt", pk=session.pk)


@login_required
def attempt(request, pk):
    session = get_object_or_404(QuizSession, pk=pk)
    # IDOR fix: only the owning student can attempt their session
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        from django.http import Http404
        raise Http404
    if session.student_id != sp.id:
        from django.http import Http404
        raise Http404
    if session.completed:
        return redirect("quiz:result", pk=pk)
    questions = session.questions.all()
    current = questions.filter(chosen="").first()
    if not current:
        return redirect("quiz:finish", pk=pk)
    answered = questions.exclude(chosen="").count()
    return render(request, "quiz/attempt.html", {
        "session": session, "question": current,
        "answered": answered, "total": session.total,
        "progress": int(answered / session.total * 100) if session.total else 0,
    })


@login_required
def answer(request, question_pk):
    chosen = request.POST.get("chosen", "")
    q = get_object_or_404(Question, pk=question_pk)
    # IDOR fix: verify the session belongs to this user
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        from django.http import Http404
        raise Http404
    if q.session.student_id != sp.id:
        from django.http import Http404
        raise Http404
    if chosen:
        submit_answer(question_pk, chosen)
    return redirect("quiz:attempt", pk=q.session_id)


@login_required
def finish(request, pk):
    session = get_object_or_404(QuizSession, pk=pk)
    # IDOR fix
    from students.models import StudentProfile
    try:
        sp = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        from django.http import Http404
        raise Http404
    if session.student_id != sp.id:
        from django.http import Http404
        raise Http404
    finish_session(pk)
    return redirect("quiz:result", pk=pk)


@login_required
def result(request, pk):
    session = get_object_or_404(QuizSession, pk=pk)
    # IDOR fix: only owner or admin/staff can view result
    if request.user.role.lower() == "student":
        from students.models import StudentProfile
        try:
            sp = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            from django.http import Http404
            raise Http404
        if session.student_id != sp.id:
            from django.http import Http404
            raise Http404
    questions = session.questions.all()
    return render(request, "quiz/result.html", {"session": session, "questions": questions})
