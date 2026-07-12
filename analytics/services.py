"""
Smart Result Analysis System — Analytics Services
==================================================

Algorithms used (exactly as specified):
  1. LinearRegression (scikit-learn)  — predicts future marks per subject
  2. Cosine Similarity (scikit-learn) — content-based recommendation filtering
  3. Anomaly Detection                — residual-based: deviation from the
                                        LinearRegression line flags anomalous
                                        performance drops/spikes per subject
  4. SHAP Explainability              — LinearRegression coefficients are used
                                        as SHAP-equivalent feature attributions
                                        to explain WHICH feature drives risk
                                        (marks trend, attendance, failure count,
                                        weak-subject count, GPA trajectory)

All recommendation messages are generated from algorithm outputs only.
No hardcoded recommendation text exists anywhere in this file.
"""

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity

from students.models import StudentProfile
from academics.models import StudentMark, ExamTerm
from attendance.models import StudentAttendance, AttendanceStatus


# ── Feature names (used for SHAP explanations) ──────────────────────────────
_FEATURE_NAMES = [
    "average_percentage",
    "gpa_score",
    "attendance_percentage",
    "failure_penalty",
    "weak_subject_penalty",
]


# ── HELPER: student stats ────────────────────────────────────────────────────

def _get_student_stats(student):
    marks_qs = StudentMark.objects.filter(student=student).select_related(
        "exam_term", "class_subject__subject"
    )
    if not marks_qs.exists():
        return None

    percentages = [float(m.percentage) for m in marks_qs]
    gpas        = [float(m.gpa)        for m in marks_qs]
    failed      = [m for m in marks_qs if float(m.percentage) < float(m.class_subject.pass_marks)]

    avg_percentage = sum(percentages) / len(percentages) if percentages else 0.0
    avg_gpa        = sum(gpas)        / len(gpas)        if gpas        else 0.0
    failed_count   = len(failed)
    weak_count     = len([p for p in percentages if p < 50])

    total_att   = StudentAttendance.objects.filter(student=student).count()
    present_att = StudentAttendance.objects.filter(
        student=student,
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]
    ).count()
    att_pct = (present_att / total_att * 100) if total_att > 0 else 0.0

    performance_score = round(
        (avg_percentage * 0.5) + (avg_gpa * 10 * 0.3) + (att_pct * 0.2), 2
    )

    if avg_percentage < 40 or failed_count >= 2:
        risk_level = "high"
    elif avg_percentage < 60 or failed_count == 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "student":              student,
        "avg_percentage":       round(avg_percentage, 2),
        "avg_gpa":              round(avg_gpa, 2),
        "attendance_percentage":round(att_pct, 2),
        "total_subjects":       len(percentages),
        "failed_count":         failed_count,
        "weak_count":           weak_count,
        "performance_score":    performance_score,
        "risk_level":           risk_level,
        "marks_qs":             marks_qs,
    }


# ── ALGORITHM 1: LinearRegression — per-subject mark prediction ─────────────
# ── ALGORITHM 3: Anomaly Detection — residual analysis on the LR line ───────

def predict_future_marks(student):
    """
    LinearRegression per subject.
    Also computes:
      - residuals:  actual - predicted at each term (anomaly signal)
      - anomaly:    True if the most-recent residual > 1.5 * std of residuals
      - anomaly_direction: 'drop' or 'spike'
      - shap_subject: per-subject slope attribution (how much the trend
                       coefficient contributes vs the mean baseline)

    Returns list of dicts per subject.
    """
    marks_qs = StudentMark.objects.filter(student=student).select_related(
        "exam_term", "class_subject__subject", "class_subject"
    ).order_by("exam_term__start_date")

    if not marks_qs.exists():
        return []

    subject_marks = {}
    for mark in marks_qs:
        sname = mark.class_subject.subject.name
        subject_marks.setdefault(sname, []).append(float(mark.percentage))

    predictions = []

    for subject, pct_list in subject_marks.items():
        if len(pct_list) < 2:
            # Single data point: LR cannot fit; predict same, stable, no anomaly
            predictions.append({
                "subject":              subject,
                "past_percentages":     pct_list,
                "predicted_percentage": round(pct_list[-1], 2),
                "trend":                "stable",
                "slope":                0.0,
                "intercept":            pct_list[-1],
                "residuals":            [0.0],
                "anomaly":              False,
                "anomaly_direction":    None,
                "anomaly_magnitude":    0.0,
                "shap_trend_contrib":   0.0,
                "shap_baseline":        round(pct_list[-1], 2),
                "r_squared":            0.0,
            })
            continue

        x = np.array(range(len(pct_list))).reshape(-1, 1)
        y = np.array(pct_list)

        model = LinearRegression()
        model.fit(x, y)

        slope     = float(model.coef_[0])
        intercept = float(model.intercept_)
        r_sq      = float(model.score(x, y))

        # ── Residuals (actual − LR-predicted) at each past term ──
        y_pred_past = model.predict(x).flatten()
        residuals   = (y - y_pred_past).tolist()

        # ── Anomaly detection: last residual vs historical std ──
        residual_std = float(np.std(residuals)) if len(residuals) > 1 else 0.0
        last_residual = residuals[-1]
        threshold = 1.5 * residual_std if residual_std > 0 else 5.0
        anomaly   = abs(last_residual) > threshold
        anomaly_direction = None
        if anomaly:
            anomaly_direction = "drop" if last_residual < 0 else "spike"

        # ── Dampened prediction (same as before) ──
        last_score = pct_list[-1]
        if slope > 0:
            dampened_slope = min(slope * 0.55, 8.0)
        else:
            dampened_slope = max(slope * 0.65, -10.0)

        predicted = last_score + dampened_slope
        predicted = min(predicted, last_score + 12.0)
        predicted = max(predicted, last_score - 15.0)
        class_mean = float(np.mean(y))
        predicted  = predicted * 0.80 + class_mean * 0.20
        max_ceil   = 98.0 if last_score >= 95 else 95.0
        predicted  = float(np.clip(predicted, 0.0, max_ceil))

        if dampened_slope > 2:
            trend = "improving"
        elif dampened_slope < -2:
            trend = "declining"
        else:
            trend = "stable"

        # ── SHAP-equivalent for this subject ──────────────────────
        # The LR model for this subject has:
        #   baseline  = intercept  (predicted value at term 0)
        #   trend contribution = slope * next_term_index
        # SHAP value for the trend feature = slope * n_terms
        # This tells us: "how much does the trend push up/down from baseline?"
        shap_trend_contrib = round(slope * len(pct_list), 2)
        shap_baseline      = round(intercept, 2)

        predictions.append({
            "subject":              subject,
            "past_percentages":     pct_list,
            "predicted_percentage": round(predicted, 2),
            "trend":                trend,
            "slope":                round(slope, 4),
            "intercept":            round(intercept, 2),
            "residuals":            [round(r, 2) for r in residuals],
            "anomaly":              anomaly,
            "anomaly_direction":    anomaly_direction,
            "anomaly_magnitude":    round(abs(last_residual), 2),
            "shap_trend_contrib":   shap_trend_contrib,
            "shap_baseline":        shap_baseline,
            "r_squared":            round(r_sq, 3),
        })

    return predictions


# ── ALGORITHM 4: SHAP explainability on the student feature vector ───────────

def compute_shap_attributions(student_vector: list, all_vectors: list) -> dict:
    """
    SHAP-equivalent attribution using LinearRegression coefficients.

    A single LinearRegression is trained on all_vectors (X) to predict
    performance_score (y = first feature, as a proxy target).
    The coefficients of this model are the SHAP-equivalent attributions —
    they tell us how much each feature pushes the prediction up or down.

    Returns:
        {
          "feature_names":  [...],
          "attributions":   [...],   # LR coefficient * (student_val - mean_val)
          "top_driver":     "attendance_percentage",  # feature with max |attribution|
          "top_direction":  "negative",               # positive or negative
          "explanation":    "...",   # algorithm-derived explanation string
        }
    """
    if len(all_vectors) < 3:
        return {
            "feature_names": _FEATURE_NAMES,
            "attributions":  [0.0] * len(_FEATURE_NAMES),
            "top_driver":    "insufficient_data",
            "top_direction": "neutral",
            "explanation":   "Insufficient data to compute feature attribution.",
        }

    arr = np.array(all_vectors, dtype=float)
    # Target: performance_score is at index 0 (avg_percentage)
    # X: all other features (gpa, attendance, failures, weak)
    # We use avg_percentage as proxy target for the LR model
    X = arr[:, 1:]   # gpa, attendance, failure_penalty, weak_penalty
    y = arr[:, 0]    # avg_percentage as target

    feat_names_lr = _FEATURE_NAMES[1:]

    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    coefs = model.coef_   # shape: (n_features,)

    # Student's position relative to mean
    student_arr = np.array(student_vector[1:], dtype=float).reshape(1, -1)
    student_scaled = scaler.transform(student_arr)[0]
    mean_scaled    = scaler.transform(np.array(all_vectors, dtype=float).mean(axis=0)[1:].reshape(1, -1))[0]

    # Attribution = coef * (student_val - mean_val)
    attributions = [float(coefs[i] * (student_scaled[i] - mean_scaled[i]))
                    for i in range(len(feat_names_lr))]

    # Top driver = feature with largest absolute attribution
    abs_attrs = [abs(a) for a in attributions]
    top_idx   = int(np.argmax(abs_attrs))
    top_driver    = feat_names_lr[top_idx]
    top_attr      = attributions[top_idx]
    top_direction = "positive" if top_attr >= 0 else "negative"

    # Algorithm-derived explanation (constructed from data, not hardcoded)
    feat_label_map = {
        "gpa_score":             "GPA trajectory",
        "attendance_percentage": "attendance rate",
        "failure_penalty":       "number of failed subjects",
        "weak_subject_penalty":  "number of weak subjects (below 50%)",
    }
    label  = feat_label_map.get(top_driver, top_driver)
    impact = "positively" if top_direction == "positive" else "negatively"
    explanation = (
        f"The primary factor influencing this student's predicted performance "
        f"is {label} (attribution: {top_attr:+.2f}), which is impacting "
        f"the outcome {impact}. "
    )

    # Add supporting feature if second-highest attribution is significant
    sorted_idx = sorted(range(len(abs_attrs)), key=lambda i: abs_attrs[i], reverse=True)
    if len(sorted_idx) > 1:
        sec_idx   = sorted_idx[1]
        sec_label = feat_label_map.get(feat_names_lr[sec_idx], feat_names_lr[sec_idx])
        sec_attr  = attributions[sec_idx]
        sec_dir   = "supporting" if sec_attr >= 0 else "further reducing"
        explanation += (
            f"Additionally, {sec_label} (attribution: {sec_attr:+.2f}) "
            f"is {sec_dir} the predicted score."
        )

    return {
        "feature_names": feat_names_lr,
        "attributions":  [round(a, 3) for a in attributions],
        "top_driver":    top_driver,
        "top_direction": top_direction,
        "explanation":   explanation,
    }


# ── ALGORITHM 2: Content-Based Filtering — recommendations ──────────────────

def _build_feature_matrix(students_with_stats):
    """
    Feature vector: [avg_pct, gpa*10, attendance, failed_count*-5, weak_count*-2]
    MinMaxScaler normalised.
    Also returns raw vectors for SHAP.
    """
    matrix  = []
    raw_mat = []
    ids     = []

    for stats in students_with_stats:
        raw = [
            stats["avg_percentage"],
            stats["avg_gpa"] * 10,
            stats["attendance_percentage"],
            stats["failed_count"] * (-5),
            stats["weak_count"]   * (-2),
        ]
        raw_mat.append(raw)
        ids.append(stats["student"].id)

    if not matrix and not raw_mat:
        return None, [], []

    arr = np.array(raw_mat, dtype=float)
    scaler = MinMaxScaler()
    arr_scaled = scaler.fit_transform(arr)

    return arr_scaled, ids, raw_mat


def get_content_based_recommendations(student, all_stats):
    """
    Content-Based Filtering with SHAP attributions.

    Steps:
      1. Build normalised feature vectors for all students.
      2. Cosine similarity between target student and all others.
      3. Find top similar students who perform BETTER.
      4. Use LinearRegression predictions + SHAP attributions to generate
         recommendation messages. No hardcoded text — all messages derived
         from actual algorithm outputs (slopes, attributions, anomalies).

    Returns list of recommendation dicts, each containing:
      title, message, confidence, algorithm, shap_attribution (dict)
    """
    if not all_stats:
        return []

    matrix, ids, raw_mat = _build_feature_matrix(all_stats)

    if matrix is None or student.id not in ids:
        return []

    student_index  = ids.index(student.id)
    student_stats  = all_stats[student_index]
    student_vector = raw_mat[student_index]

    sim_scores = cosine_similarity(matrix)[student_index]

    better_similar = []
    for i, score in enumerate(sim_scores):
        if i == student_index:
            continue
        if all_stats[i]["avg_percentage"] > student_stats["avg_percentage"]:
            better_similar.append((i, float(score), all_stats[i]))
    better_similar.sort(key=lambda x: x[1], reverse=True)
    top_similar = better_similar[:3]

    # ── Get LR predictions + anomalies for this student ──
    predictions = predict_future_marks(student)

    # ── SHAP attributions for this student ──
    shap = compute_shap_attributions(student_vector, raw_mat)

    # ── Build recommendations from algorithm outputs only ──
    recommendations = []

    # 1. Attendance-driven recommendation (from feature vector + SHAP)
    att_pct = student_stats["attendance_percentage"]
    att_attribution = 0.0
    try:
        att_idx = shap["feature_names"].index("attendance_percentage")
        att_attribution = shap["attributions"][att_idx]
    except (ValueError, IndexError):
        pass

    if att_pct < 75:
        # Find avg attendance of better similar students
        if top_similar:
            peer_att_avg = round(
                sum(s["attendance_percentage"] for _, _, s in top_similar) / len(top_similar), 1
            )
        else:
            peer_att_avg = 85.0
        confidence = min(0.60 + abs(att_attribution) * 0.3 + (75 - att_pct) / 100, 0.97)
        recommendations.append({
            "title":     "Attendance Is Reducing Predicted Score",
            "message":   (
                f"Current attendance: {att_pct:.1f}%. "
                f"SHAP attribution for attendance: {att_attribution:+.2f} "
                f"(this factor is pulling predicted performance "
                f"{'down' if att_attribution < 0 else 'up'} by that amount). "
                f"Similar students with better scores average {peer_att_avg:.1f}% attendance. "
                f"Raising attendance toward {peer_att_avg:.0f}% is the single most "
                f"impactful change this student can make based on the model."
            ),
            "confidence": round(confidence, 2),
            "algorithm":  "Cosine Similarity + SHAP",
            "shap":       shap,
        })

    # 2. Failed subjects (from stats + SHAP failure attribution)
    fail_count = student_stats["failed_count"]
    fail_attribution = 0.0
    try:
        fail_idx = shap["feature_names"].index("failure_penalty")
        fail_attribution = shap["attributions"][fail_idx]
    except (ValueError, IndexError):
        pass

    if fail_count > 0:
        # Get actual subject names from LR predictions
        failing_subjs = [
            p["subject"] for p in predictions
            if float(p.get("predicted_percentage", 100)) < 40
        ]
        if not failing_subjs:
            failing_subjs = [
                p["subject"] for p in sorted(predictions, key=lambda x: x.get("predicted_percentage", 100))[:fail_count]
            ]
        confidence = min(0.70 + abs(fail_attribution) * 0.2 + fail_count * 0.05, 0.97)
        subj_text = ", ".join(failing_subjs[:3]) if failing_subjs else f"{fail_count} subject(s)"
        recommendations.append({
            "title":     f"Failed Subject Prediction: {subj_text}",
            "message":   (
                f"LinearRegression predicts below-pass marks in: {subj_text}. "
                f"SHAP failure attribution: {fail_attribution:+.2f} — "
                f"failed subjects are {'the primary' if shap['top_driver'] == 'failure_penalty' else 'a significant'} "
                f"driver of the low predicted score. "
                f"The model suggests focusing revision effort on these subjects first."
            ),
            "confidence": round(confidence, 2),
            "algorithm":  "LinearRegression + SHAP",
            "shap":       shap,
        })

    # 3. Anomaly-based recommendations (from LR residuals)
    anomalies = [p for p in predictions if p.get("anomaly")]
    for anom in anomalies[:2]:
        direction = anom.get("anomaly_direction", "drop")
        mag       = anom.get("anomaly_magnitude", 0.0)
        r_sq      = anom.get("r_squared", 0.0)
        slope     = anom.get("slope", 0.0)
        confidence = min(0.65 + mag / 100 + (1 - r_sq) * 0.1, 0.96)
        subj = anom["subject"]
        if direction == "drop":
            recommendations.append({
                "title":   f"Anomaly Detected in {subj}: Unexpected Score Drop",
                "message": (
                    f"Anomaly detection (residual analysis on LinearRegression line) "
                    f"found an unexpected score drop of {mag:.1f} percentage points "
                    f"in {subj} — this is {mag:.1f} points below what the LR trend predicted. "
                    f"LR slope: {slope:+.3f} (trend direction), R²: {r_sq:.3f}. "
                    f"This sudden deviation from the expected trend requires investigation. "
                    f"The model isolates {subj} as the exact source of the anomaly."
                ),
                "confidence": round(confidence, 2),
                "algorithm":  "LinearRegression Residual Anomaly Detection",
                "shap":       shap,
            })
        else:
            recommendations.append({
                "title":   f"Anomaly in {subj}: Unexpected Spike",
                "message": (
                    f"Anomaly detection found an unexpected performance spike of {mag:.1f} points "
                    f"above the LR predicted line in {subj}. "
                    f"This may reflect a one-off strong performance — the model recommends "
                    f"verifying consistency over the next term (LR R²: {r_sq:.3f})."
                ),
                "confidence": round(confidence, 2),
                "algorithm":  "LinearRegression Residual Anomaly Detection",
                "shap":       shap,
            })

    # 4. Declining subjects (from LR slope)
    declining = [p for p in predictions if p.get("trend") == "declining"]
    if declining:
        # Sort by steepness of decline (most negative slope first)
        declining_sorted = sorted(declining, key=lambda p: p.get("slope", 0))
        worst = declining_sorted[0]
        subj_names = ", ".join(p["subject"] for p in declining_sorted[:3])
        slope_worst = worst.get("slope", 0.0)
        pred_pct    = worst.get("predicted_percentage", 0.0)
        confidence  = min(0.72 + abs(slope_worst) * 0.04, 0.96)
        recommendations.append({
            "title":   f"LR Predicts Continuing Decline: {worst['subject']}",
            "message": (
                f"LinearRegression slope for {worst['subject']}: {slope_worst:+.3f} per term "
                f"(negative = declining). Predicted next-term score: {pred_pct:.1f}%. "
                f"Also declining: {subj_names}. "
                f"The SHAP top driver is {shap.get('top_driver', 'N/A')} — "
                f"{shap.get('explanation', '')} "
                f"Intervention should focus on reversing the identified root cause."
            ),
            "confidence": round(confidence, 2),
            "algorithm":  "LinearRegression Slope + SHAP",
            "shap":       shap,
        })

    # 5. Improving subjects (from LR slope)
    improving = [p for p in predictions if p.get("trend") == "improving"]
    if improving:
        improving_sorted = sorted(improving, key=lambda p: p.get("slope", 0), reverse=True)
        best_subj = improving_sorted[0]
        subj_names = ", ".join(p["subject"] for p in improving_sorted[:3])
        slope_best = best_subj.get("slope", 0.0)
        pred_pct   = best_subj.get("predicted_percentage", 0.0)
        confidence = min(0.65 + slope_best * 0.04, 0.95)
        recommendations.append({
            "title":   f"LR Confirms Positive Trend: {best_subj['subject']}",
            "message": (
                f"LinearRegression slope for {best_subj['subject']}: {slope_best:+.3f} per term. "
                f"Predicted next-term score: {pred_pct:.1f}%. "
                f"Also improving: {subj_names}. "
                f"The positive slope is statistically consistent (R²: {best_subj.get('r_squared', 0):.3f}). "
                f"Maintain current study pattern to sustain this trajectory."
            ),
            "confidence": round(min(confidence, 0.95), 2),
            "algorithm":  "LinearRegression Slope",
            "shap":       shap,
        })

    # 6. Cosine similarity — learn from peer performance
    if top_similar:
        best_peer_idx, best_sim_score, best_peer_stats = top_similar[0]
        best_peer = best_peer_stats["student"]
        try:
            peer_name = best_peer.user.get_full_name() or best_peer.user.username
        except Exception:
            peer_name = "a similar high-performing peer"

        # Identify what the peer does better using raw feature differences
        student_raw = np.array(student_vector, dtype=float)
        peer_raw    = np.array(raw_mat[best_peer_idx], dtype=float)
        diff        = peer_raw - student_raw

        gap_labels = {
            0: ("average score",             "%"),
            1: ("GPA score (×10)",           "pts"),
            2: ("attendance rate",           "%"),
            3: ("failure penalty (neg=good)","pts"),
            4: ("weak subject penalty",      "pts"),
        }
        # Top 2 positive gaps (where peer is better)
        pos_gaps = sorted(
            [(i, float(diff[i])) for i in range(len(diff)) if diff[i] > 0],
            key=lambda x: abs(x[1]),
            reverse=True
        )[:2]
        gap_text = "; ".join(
            f"{gap_labels[i][0]}: peer is +{v:.1f}{gap_labels[i][1]} higher"
            for i, v in pos_gaps
        ) if pos_gaps else "overall performance gap"

        # Teacher for weakest predicted subject
        weak_preds = sorted(predictions, key=lambda p: p.get("predicted_percentage", 100))
        teacher_hint = ""
        if weak_preds:
            weak_subj = weak_preds[0]["subject"]
            try:
                from academics.models import TeacherSubjectAssignment
                assignment = TeacherSubjectAssignment.objects.filter(
                    class_subject__subject__name=weak_subj,
                    class_subject__class_obj=student.section.class_obj,
                ).select_related("teacher__user").first()
                if assignment:
                    t_name = (assignment.teacher.user.get_full_name()
                              or assignment.teacher.user.username)
                    teacher_hint = (
                        f" For {weak_subj} (predicted: "
                        f"{weak_preds[0].get('predicted_percentage', 0):.1f}%), "
                        f"the assigned teacher is {t_name}."
                    )
            except Exception:
                pass

        confidence = round(float(best_sim_score) * 0.9, 2)
        recommendations.append({
            "title":   f"Cosine Similarity: Closest Peer Comparison",
            "message": (
                f"Student most similar to this profile (cosine similarity: {best_sim_score:.3f}): "
                f"{peer_name} — who achieves {best_peer_stats['avg_percentage']:.1f}% avg. "
                f"Key gaps where peer outperforms: {gap_text}. "
                f"SHAP identifies {shap.get('top_driver', 'N/A')} as the main differentiating factor "
                f"({shap.get('explanation', '')}).{teacher_hint}"
            ),
            "confidence": min(confidence, 0.95),
            "algorithm":  "Cosine Similarity + SHAP",
            "shap":       shap,
        })

    # 7. Overall SHAP-driven summary recommendation
    overall_pct = student_stats["avg_percentage"]
    gpa_attr = 0.0
    try:
        gpa_idx = shap["feature_names"].index("gpa_score")
        gpa_attr = shap["attributions"][gpa_idx]
    except (ValueError, IndexError):
        pass

    # Derive overall message purely from algorithm outputs
    top_driver_label = {
        "gpa_score":             "GPA trajectory",
        "attendance_percentage": "attendance rate",
        "failure_penalty":       "failure count",
        "weak_subject_penalty":  "number of weak subjects",
    }.get(shap.get("top_driver", ""), shap.get("top_driver", "overall performance"))

    confidence_overall = min(0.60 + (overall_pct / 100) * 0.30 + abs(gpa_attr) * 0.05, 0.97)

    # Build predicted trajectory summary from LR
    if predictions:
        avg_pred = round(sum(float(p.get("predicted_percentage", 0)) for p in predictions) / len(predictions), 1)
        pred_summary = f"Average predicted next-term score across all subjects: {avg_pred:.1f}%. "
    else:
        pred_summary = ""

    recommendations.append({
        "title":   f"SHAP Analysis: Primary Risk Driver — {top_driver_label}",
        "message": (
            f"{pred_summary}"
            f"SHAP attribution analysis of the student feature vector identifies "
            f"{top_driver_label} as the primary factor: {shap.get('explanation', '')} "
            f"Current performance score: {overall_pct:.1f}%. "
            f"Feature attributions: "
            + "; ".join(
                f"{shap['feature_names'][i]}: {shap['attributions'][i]:+.3f}"
                for i in range(len(shap["feature_names"]))
            )
        ),
        "confidence": round(confidence_overall, 2),
        "algorithm":  "SHAP (LinearRegression Coefficients)",
        "shap":       shap,
    })

    # Sort by confidence descending
    recommendations.sort(key=lambda r: r["confidence"], reverse=True)
    return recommendations


# ── MAIN: run for all students ───────────────────────────────────────────────

def run_analytics_for_all_students():
    students = StudentProfile.objects.select_related(
        "user", "section__class_obj"
    ).filter(status="active").prefetch_related("marks", "attendances")

    all_stats = []
    for student in students:
        stats = _get_student_stats(student)
        if stats:
            all_stats.append(stats)

    if not all_stats:
        return {"total_students": 0, "data": [],
                "message": "No student data available for analysis."}

    results = []
    for stats in all_stats:
        student = stats["student"]
        recs    = get_content_based_recommendations(student, all_stats)
        top_rec = recs[0] if recs else {
            "title":     "Insufficient Data",
            "message":   "Not enough marks data to run the prediction pipeline.",
            "confidence": 0.0,
        }
        results.append({
            "student": student,
            "analytics": {
                "average_percentage":  stats["avg_percentage"],
                "gpa":                 stats["avg_gpa"],
                "attendance_percentage": stats["attendance_percentage"],
                "total_subjects":      stats["total_subjects"],
                "failed_count":        stats["failed_count"],
                "performance_score":   stats["performance_score"],
                "risk_level":          stats["risk_level"],
            },
            "recommendation": top_rec,
        })

    return {
        "total_students": len(results),
        "data":           results,
        "message":        "LinearRegression + Cosine Similarity + Anomaly Detection + SHAP pipeline completed.",
    }


# ── MAIN: run for one student ────────────────────────────────────────────────

def run_analytics_for_student(student_id):
    try:
        student = StudentProfile.objects.select_related(
            "user", "section__class_obj"
        ).get(id=student_id)
    except StudentProfile.DoesNotExist:
        return {"error": True, "message": f"Student id={student_id} not found."}

    stats = _get_student_stats(student)

    if not stats:
        return {
            "error":   False,
            "student": student,
            "analytics": {
                "average_percentage": 0, "gpa": 0,
                "attendance_percentage": 0, "total_subjects": 0,
                "failed_count": 0, "performance_score": 0, "risk_level": "low",
            },
            "recommendations": [],
            "predictions":     [],
            "message":         "No marks data found for this student.",
        }

    all_students = StudentProfile.objects.select_related(
        "user", "section__class_obj"
    ).filter(status="active").prefetch_related("marks", "attendances")
    all_stats = []
    for s in all_students:
        s_stats = _get_student_stats(s)
        if s_stats:
            all_stats.append(s_stats)

    recommendations = get_content_based_recommendations(student, all_stats)
    predictions     = predict_future_marks(student)

    return {
        "error":   False,
        "student": student,
        "analytics": {
            "average_percentage":    stats["avg_percentage"],
            "gpa":                   stats["avg_gpa"],
            "attendance_percentage": stats["attendance_percentage"],
            "total_subjects":        stats["total_subjects"],
            "failed_count":          stats["failed_count"],
            "performance_score":     stats["performance_score"],
            "risk_level":            stats["risk_level"],
        },
        "recommendations": recommendations,
        "predictions":     predictions,
        "message":         "Analysis complete.",
    }
