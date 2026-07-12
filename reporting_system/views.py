# -*- coding: utf-8 -*-
import io
import logging
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse, Http404

from academics.models import ExamTerm, StudentMark
from students.models import StudentProfile

from .models import (
    StudentResult,
    ClassResultSummary,
    ResultCalculationLog,
)

logger = logging.getLogger(__name__)


# =====================================================
# DASHBOARD (REPORTING OVERVIEW)
# =====================================================
@login_required
@user_passes_test(lambda u: u.is_authenticated and u.role.lower() in ("admin", "staff", "accountant"))
def reporting_dashboard(request):

    try:
        data = {
            "total_results": StudentResult.objects.count(),
            "total_students": StudentProfile.objects.count(),
            "latest_term": ExamTerm.objects.order_by("-start_date").first(),
            "latest_summary": ClassResultSummary.objects.order_by("-id").first(),
        }

        return render(request, "reporting/dashboard.html", data)

    except Exception:
        logger.exception("Reporting dashboard failed")
        messages.error(request, "Failed to load reporting dashboard")
        return render(request, "reporting/dashboard.html", {})


# =====================================================
# STUDENT RESULT LIST
# =====================================================
@login_required
def student_results(request):

    results = StudentResult.objects.select_related(
        "student",
        "exam_term"
    ).all().order_by("-created_at")

    term_id = request.GET.get("term")

    if term_id:
        results = results.filter(exam_term_id=term_id)

    return render(request, "reporting/student_results.html", {
        "results": results,
        "terms": ExamTerm.objects.all(),
    })


# =====================================================
# STUDENT RESULT DETAIL
# =====================================================
@login_required
def student_result_detail(request, pk):

    result = get_object_or_404(StudentResult, pk=pk)

    marks = StudentMark.objects.filter(
        student=result.student,
        exam_term=result.exam_term
    ).select_related("class_subject")

    return render(request, "reporting/student_result_detail.html", {
        "result": result,
        "marks": marks,
    })


# =====================================================
# CLASS SUMMARY LIST
# =====================================================
@login_required
def academic_summary_list(request):

    summaries = ClassResultSummary.objects.select_related(
        "academic_year",
        "class_obj",
        "exam_term"
    ).all().order_by("-id")

    return render(request, "reporting/academic_summary_list.html", {
        "summaries": summaries
    })


# =====================================================
# AUDIT LOG VIEW (UPDATED)
# =====================================================
@login_required
def audit_logs(request):

    logs = ResultCalculationLog.objects.select_related(
        "student",
        "exam_term"
    ).all().order_by("-created_at")

    model_filter = request.GET.get("model")

    if model_filter:
        logs = logs.filter(action=model_filter)

    return render(request, "reporting/audit_logs.html", {
        "logs": logs
    })


# =====================================================
# RESULT REBUILD — ADMIN ONLY, heavy operation
# =====================================================
@login_required
@user_passes_test(lambda u: u.is_authenticated and u.role.lower() == "admin")
def rebuild_results(request):

    if request.method != "POST":
        return redirect("reporting_system:reporting_dashboard")

    try:
        from reporting_system.services import ResultService

        students = StudentProfile.objects.all()
        terms = ExamTerm.objects.all()

        count = 0

        for student in students:
            for term in terms:

                marks = StudentMark.objects.filter(
                    student=student,
                    exam_term=term
                )

                if not marks.exists():
                    continue

                ResultService.generate_student_result(student, term)
                count += 1

        messages.success(request, f"{count} results rebuilt successfully")

    except Exception:
        logger.exception("Rebuild failed")
        messages.error(request, "Failed to rebuild results")

    return redirect("reporting_system:reporting_dashboard")


# =====================================================
# MY RESULTS -- STUDENT SEES ONLY THEIR OWN RESULTS
# =====================================================
@login_required
def my_results(request):
    """
    Student views only their own exam results.
    Filters by the StudentProfile linked to request.user.
    """
    try:
        student = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile linked to your account.")
        return redirect("accounts:student_dashboard")

    results = StudentResult.objects.filter(
        student=student
    ).select_related("exam_term").order_by("-exam_term__start_date")

    term_id = request.GET.get("term")
    if term_id:
        results = results.filter(exam_term_id=term_id)

    terms = ExamTerm.objects.all().order_by("-start_date")

    return render(request, "reporting/my_results.html", {
        "student": student,
        "results": results,
        "terms":   terms,
        "selected_term": term_id,
    })


# =====================================================
# DOWNLOAD RESULT PDF -- STUDENT DOWNLOADS THEIR REPORT
# =====================================================
@login_required
def download_result_pdf(request, result_pk):
    """
    Generates and streams a professional PDF report for a StudentResult.
    Only the owning student (or admin/staff) can download it.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )

    result = get_object_or_404(StudentResult, pk=result_pk)

    # Security: students can only download their own result
    if request.user.role == "student":
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            raise Http404
        if result.student != student_profile:
            raise Http404

    student = result.student
    term    = result.exam_term

    # Subject-wise marks
    marks = StudentMark.objects.filter(
        student=student,
        exam_term=term,
    ).select_related("class_subject__subject", "class_subject").order_by(
        "class_subject__subject__name"
    )

    # AI recommendations -- generated live by the ML pipeline
    # (same engine used by the AI Report page)
    recommendations = []
    predictions     = []
    analytics_data  = {}
    try:
        from analytics.services import run_analytics_for_student
        ai_result      = run_analytics_for_student(student.id)
        recommendations = ai_result.get("recommendations", [])   # list of dicts
        predictions     = ai_result.get("predictions", [])
        analytics_data  = ai_result.get("analytics", {})
    except Exception:
        pass

    
    #  Build PDF in memory                                                 #
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    # Colour palette
    DARK_BLUE  = colors.HexColor("#1a3c6e")
    LIGHT_BLUE = colors.HexColor("#dbeafe")
    GREEN      = colors.HexColor("#16a34a")
    RED        = colors.HexColor("#dc2626")
    AMBER      = colors.HexColor("#d97706")
    GREY_LIGHT = colors.HexColor("#f1f5f9")
    GREY_MID   = colors.HexColor("#94a3b8")
    WHITE      = colors.white
    BLACK      = colors.black

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "RPTitle", parent=styles["Normal"],
        fontSize=20, textColor=WHITE,
        fontName="Helvetica-Bold", alignment=TA_CENTER,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "RPSubtitle", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#bfdbfe"),
        fontName="Helvetica", alignment=TA_CENTER,
    )
    section_heading = ParagraphStyle(
        "RPSection", parent=styles["Normal"],
        fontSize=12, textColor=DARK_BLUE,
        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "RPBody", parent=styles["Normal"],
        fontSize=9.5, textColor=BLACK,
        fontName="Helvetica", leading=14,
    )
    center_style = ParagraphStyle(
        "RPCenter", parent=body_style, alignment=TA_CENTER,
    )
    small_grey = ParagraphStyle(
        "RPSmall", parent=styles["Normal"],
        fontSize=8, textColor=GREY_MID,
        fontName="Helvetica", alignment=TA_RIGHT,
    )
    rec_title_style = ParagraphStyle(
        "RPRecTitle", parent=styles["Normal"],
        fontSize=10, textColor=DARK_BLUE,
        fontName="Helvetica-Bold", spaceAfter=2,
    )
    rec_body_style = ParagraphStyle(
        "RPRecBody", parent=styles["Normal"],
        fontSize=9, textColor=BLACK,
        fontName="Helvetica", leading=13,
    )

    story = []

    # ---- HEADER BANNER
    header_inner = [
        [Paragraph("Scholaro ERP", title_style)],
        [Paragraph("Academic Result Report", subtitle_style)],
    ]
    header_inner_table = Table(header_inner, colWidths=["100%"])
    header_inner_table.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    header_wrap = Table([[header_inner_table]], colWidths=["100%"])
    header_wrap.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
    ]))
    story.append(header_wrap)
    story.append(Spacer(1, 0.4 * cm))

    # ---- STUDENT INFO
    story.append(Paragraph("Student Information", section_heading))

    section_name = str(student.section) if student.section else "-"
    class_name   = str(student.section.class_obj) if student.section else "-"
    gender_val   = student.get_gender_display() if hasattr(student, "get_gender_display") else (student.gender or "-")

    info_rows = [
        ["Student Name",  student.name or str(student),  "Student ID",    student.student_id or "-"],
        ["Class",         class_name,                     "Section",       section_name],
        ["Roll Number",   student.roll_number or "-",     "Gender",        gender_val],
        ["Exam Term",     str(term),                      "Academic Year", str(term.academic_year)],
        ["Term Period",   "{} to {}".format(term.start_date, term.end_date),
                          "Published",    "Yes" if term.is_published else "No"],
    ]

    info_table = Table(
        [[Paragraph("<b>{}</b>".format(r[0]), body_style),
          Paragraph(str(r[1]), body_style),
          Paragraph("<b>{}</b>".format(r[2]), body_style),
          Paragraph(str(r[3]), body_style)]
         for r in info_rows],
        colWidths=[3.8 * cm, 6.5 * cm, 3.8 * cm, 5.5 * cm],
    )
    info_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GREY_LIGHT]),
        ("GRID",           (0, 0), (-1, -1), 0.4, GREY_MID),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4 * cm))

    # ---- OVERALL SUMMARY 
    story.append(Paragraph("Overall Result Summary", section_heading))

    pass_color = GREEN if result.is_pass else RED
    pass_text  = "PASS" if result.is_pass else "FAIL"

    pass_style = ParagraphStyle(
        "RPPassFail", parent=center_style,
        textColor=pass_color, fontName="Helvetica-Bold",
    )

    summary_data = [
        [
            Paragraph("<b>Total Marks</b>", center_style),
            Paragraph("<b>Percentage</b>",  center_style),
            Paragraph("<b>GPA</b>",         center_style),
            Paragraph("<b>Grade</b>",       center_style),
            Paragraph("<b>Result</b>",      center_style),
        ],
        [
            Paragraph("{} / {}".format(result.total_obtained_marks, result.total_full_marks), center_style),
            Paragraph("{}%".format(result.percentage), center_style),
            Paragraph(str(result.gpa), center_style),
            Paragraph(result.grade or "-", center_style),
            Paragraph(pass_text, pass_style),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[3.9 * cm] * 5)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("BACKGROUND",    (0, 1), (-1, 1), LIGHT_BLUE),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, GREY_MID),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.4 * cm))

    # ---- SUBJECT-WISE MARKS TABLE 
    story.append(Paragraph("Subject-wise Marks", section_heading))

    hdr_style = ParagraphStyle(
        "RPHdr", parent=center_style,
        textColor=WHITE, fontName="Helvetica-Bold",
    )

    col_headers = [
        Paragraph("<b>Subject</b>",    ParagraphStyle("RPH0", parent=body_style,   textColor=WHITE, fontName="Helvetica-Bold")),
        Paragraph("<b>Theory</b>",     hdr_style),
        Paragraph("<b>Practical</b>",  hdr_style),
        Paragraph("<b>Total</b>",      hdr_style),
        Paragraph("<b>Full Marks</b>", hdr_style),
        Paragraph("<b>%</b>",          hdr_style),
        Paragraph("<b>Grade</b>",      hdr_style),
        Paragraph("<b>Status</b>",     hdr_style),
    ]

    marks_rows  = [col_headers]
    row_bg_list = []

    for i, m in enumerate(marks):
        pct = float(m.percentage)
        pct_color = GREEN if pct >= 75 else (AMBER if pct >= 40 else RED)

        pass_mark   = float(m.class_subject.pass_marks) if m.class_subject else 40
        is_sub_pass = float(m.total_marks) >= pass_mark
        status_text  = "Pass" if is_sub_pass else "Fail"
        status_color = GREEN if is_sub_pass else RED

        # Build hex strings without leading '#'
        pct_hex    = pct_color.hexval().lstrip("#")
        status_hex = status_color.hexval().lstrip("#")

        marks_rows.append([
            Paragraph(m.class_subject.subject.name, body_style),
            Paragraph(str(m.theory_marks),    center_style),
            Paragraph(str(m.practical_marks), center_style),
            Paragraph("<b>{}</b>".format(m.total_marks), center_style),
            Paragraph(str(m.class_subject.full_marks), center_style),
            Paragraph("<font color='#{}'>{:.1f}%</font>".format(pct_hex, pct), center_style),
            Paragraph("<b>{}</b>".format(m.grade), center_style),
            Paragraph("<font color='{}'>{}</font>".format(status_color, status_text), center_style),
        ])
        row_bg_list.append(WHITE if i % 2 == 0 else GREY_LIGHT)

    marks_table = Table(
        marks_rows,
        colWidths=[5.0 * cm, 1.8 * cm, 2.0 * cm, 1.8 * cm, 2.2 * cm, 1.8 * cm, 1.6 * cm, 1.6 * cm],
        repeatRows=1,
    )

    marks_ts = [
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.4, GREY_MID),
    ]
    for idx, bg in enumerate(row_bg_list, start=1):
        marks_ts.append(("BACKGROUND", (0, idx), (-1, idx), bg))

    marks_table.setStyle(TableStyle(marks_ts))
    story.append(marks_table)
    story.append(Spacer(1, 0.5 * cm))

    # ---- ML PREDICTIONS (NEXT TERM FORECAST) -------------------------- #
    if predictions:
        story.append(HRFlowable(width="100%", thickness=1, color=GREY_MID))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("AI Subject Performance Forecast (Next Term)", section_heading))

        trend_note = ParagraphStyle(
            "RPTrendNote", parent=body_style,
            fontSize=8.5, textColor=GREY_MID, spaceAfter=6,
        )
        story.append(Paragraph(
            "Predicted marks are generated by a Scikit-learn Linear Regression model "
            "trained on this student's past exam history.",
            trend_note,
        ))

        pred_hdr_style = ParagraphStyle(
            "RPPredHdr", parent=center_style,
            textColor=WHITE, fontName="Helvetica-Bold",
        )
        pred_headers = [
            Paragraph("<b>Subject</b>",          ParagraphStyle("RPP0", parent=body_style, textColor=WHITE, fontName="Helvetica-Bold")),
            Paragraph("<b>Past Avg %</b>",        pred_hdr_style),
            Paragraph("<b>Predicted %</b>",       pred_hdr_style),
            Paragraph("<b>Trend</b>",             pred_hdr_style),
        ]

        pred_rows  = [pred_headers]
        pred_bg    = []

        TREND_COLORS = {
            "improving": GREEN,
            "declining": RED,
            "stable":    AMBER,
        }

        for i, p in enumerate(predictions):
            trend_val   = p.get("trend", "stable")
            trend_color = TREND_COLORS.get(trend_val, AMBER)
            past_list   = p.get("past_percentages", [])
            past_avg    = round(sum(past_list) / len(past_list), 1) if past_list else 0.0
            pred_pct    = p.get("predicted_percentage", 0.0)

            pred_rows.append([
                Paragraph(p.get("subject", "-"), body_style),
                Paragraph("{:.1f}%".format(past_avg), center_style),
                Paragraph("<b>{:.1f}%</b>".format(pred_pct), center_style),
                Paragraph(
                    "<font color='{}'>{}</font>".format(trend_color, trend_val.capitalize()),
                    center_style,
                ),
            ])
            pred_bg.append(WHITE if i % 2 == 0 else GREY_LIGHT)

        pred_table = Table(
            pred_rows,
            colWidths=[8.0 * cm, 3.5 * cm, 3.5 * cm, 4.6 * cm],
            repeatRows=1,
        )
        pred_ts = [
            ("BACKGROUND",    (0, 0), (-1, 0), DARK_BLUE),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("GRID",          (0, 0), (-1, -1), 0.4, GREY_MID),
        ]
        for idx, bg in enumerate(pred_bg, start=1):
            pred_ts.append(("BACKGROUND", (0, idx), (-1, idx), bg))
        pred_table.setStyle(TableStyle(pred_ts))
        story.append(pred_table)
        story.append(Spacer(1, 0.4 * cm))

    # ---- AI RECOMMENDATIONS
    story.append(HRFlowable(width="100%", thickness=1, color=GREY_MID))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("AI-Powered Recommendations", section_heading))

    if recommendations:
        for rec in recommendations:
            # rec is a plain dict: {"title": ..., "message": ..., "confidence": ...}
            confidence_pct = int(float(rec.get("confidence", 0)) * 100)
            algorithm_name = rec.get("algorithm", "Content-Based + Scikit-learn")
            rec_meta_style = ParagraphStyle(
                "RPRecMeta", parent=small_grey,
                alignment=TA_LEFT, textColor=GREY_MID, fontSize=7.5,
            )
            rec_block = [
                Paragraph("* {}".format(rec.get("title", "")), rec_title_style),
                Paragraph(rec.get("message", ""), rec_body_style),
                Paragraph(
                    "Confidence: {}%  |  Algorithm: {}".format(confidence_pct, algorithm_name),
                    rec_meta_style,
                ),
                Spacer(1, 0.25 * cm),
            ]
            story.append(KeepTogether(rec_block))
    else:
        story.append(Paragraph(
            "Insufficient marks data to generate AI recommendations for this term. "
            "Recommendations are generated once marks are recorded across multiple subjects.",
            body_style,
        ))

    story.append(Spacer(1, 0.5 * cm))

   
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_MID))
    story.append(Spacer(1, 0.2 * cm))

    footer_left  = ParagraphStyle("RPFootL", parent=small_grey, alignment=TA_LEFT)
    footer_right = ParagraphStyle("RPFootR", parent=small_grey, alignment=TA_RIGHT)

    footer_table = Table(
        [[
            Paragraph("Scholaro ERP -- Confidential Academic Document", footer_left),
            Paragraph("Generated on: {}".format(date.today().strftime("%B %d, %Y")), footer_right),
        ]],
        colWidths=["60%", "40%"],
    )
    footer_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(footer_table)

    
    doc.build(story)
    buffer.seek(0)

    filename = "result_{}_{}.pdf".format(
        student.student_id or student.pk,
        term.name.replace(" ", "_"),
    )

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)
    return response
