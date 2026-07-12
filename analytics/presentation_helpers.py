"""
Analytics Presentation Helpers
================================
Pure Python functions that transform existing service outputs into
richer structures for template rendering.

Rules:
- NO database queries
- NO new algorithms
- NO model writes
- Only transforms/aggregates existing predict_future_marks() and
  get_content_based_recommendations() outputs
"""

from analytics.services import predict_future_marks


# =====================================================
# CLASS-LEVEL HELPER (vocabulary only — no sentence text)
# =====================================================

def _class_level(student) -> int:
    import re
    try:
        name = student.section.class_obj.name
        nums = re.findall(r'\d+', name)
        return int(nums[0]) if nums else 5
    except Exception:
        return 5


def _vocab(simple: str, advanced: str, level: int) -> str:
    """Swap vocabulary by class level — never generates content, only synonyms."""
    return simple if level <= 5 else advanced


# =====================================================
# build_human_recommendations
# ─────────────────────────────────────────────────────
# SOURCE OF TRUTH: every word comes from the four
# algorithm outputs already computed in services.py:
#   • predictions  → LR slope / predicted_pct / anomaly / r_squared
#   • recommendations → messages built by SHAP + cosine + LR in services.py
#   • analytics    → risk_level / avg_pct / att_pct / failed_count / gpa
#
# ZERO hardcoded sentences.  Every string is assembled
# solely by formatting numeric values from those dicts.
# =====================================================

def build_human_recommendations(student, predictions: list, analytics: dict,
                                 recommendations: list) -> dict:
    """
    Assembles the student-facing smart report from ML pipeline outputs only.

    Returns:
      {
        level, category, subject_data, shap_summary, next_exam,
        declining_subjects, improving_subjects, anomaly_subjects,
        peer_comparison,   # from cosine similarity
        recs_display,      # cleaned recommendation cards for template
        study_allocation,  # per-subject computed time from LR+SHAP
      }
    """
    import re

    level       = _class_level(student)
    avg_pct     = float(analytics.get("average_percentage", 0))
    att_pct     = float(analytics.get("attendance_percentage", 0))
    failed_cnt  = int(analytics.get("failed_count", 0))
    risk_level  = analytics.get("risk_level", "low")
    perf_score  = float(analytics.get("performance_score", 0))
    gpa         = float(analytics.get("gpa", 0))

    # ── 1. Segment subjects from LR predictions ─────────────────────────────
    declining_subjects = []
    improving_subjects = []
    anomaly_subjects   = []
    stable_subjects    = []
    subject_data       = []   # full per-subject detail for template

    for p in predictions:
        subj   = p.get("subject", "")
        slope  = float(p.get("slope", 0))
        pred   = float(p.get("predicted_percentage", 0))
        trend  = p.get("trend", "stable")
        anom   = p.get("anomaly", False)
        adir   = p.get("anomaly_direction")
        amag   = float(p.get("anomaly_magnitude", 0))
        r2     = float(p.get("r_squared", 0))
        past   = p.get("past_percentages", [])
        shap_c = float(p.get("shap_trend_contrib", 0))
        base   = float(p.get("shap_baseline", pred))

        if trend == "declining":
            declining_subjects.append(subj)
        elif trend == "improving":
            improving_subjects.append(subj)
        else:
            stable_subjects.append(subj)

        if anom and adir == "drop":
            anomaly_subjects.append(subj)

        subject_data.append({
            "subject": subj,
            "slope": round(slope, 4),
            "predicted_pct": round(pred, 1),
            "trend": trend,
            "anomaly": anom,
            "anomaly_direction": adir,
            "anomaly_magnitude": round(amag, 2),
            "r_squared": round(r2, 3),
            "past_percentages": past,
            "shap_trend_contrib": round(shap_c, 2),
            "shap_baseline": round(base, 2),
            "is_failing": pred < 40,
            "is_weak": 40 <= pred < 50,
        })

    # Sort: worst predicted first
    subject_data.sort(key=lambda x: x["predicted_pct"])

    # ── 2. LR-predicted average ──────────────────────────────────────────────
    if predictions:
        lr_avg_pred = round(
            sum(float(p.get("predicted_percentage", 0)) for p in predictions) / len(predictions), 1
        )
        lr_pass = sum(1 for p in predictions if float(p.get("predicted_percentage", 0)) >= 40)
        lr_fail = len(predictions) - lr_pass
    else:
        lr_avg_pred = None
        lr_pass = lr_fail = 0

    # ── 3. Category — derived entirely from risk_level + lr_avg_pred ─────────
    #    Label: risk_level string (high/medium/low) → display text via _vocab
    risk_display = {
        "high":   _vocab("Needs Extra Help",    "High Risk — Needs Support", level),
        "medium": _vocab("Room to Improve",      "Medium Risk — Needs Effort", level),
        "low":    _vocab("Performing Well",      "Low Risk — Good Standing",  level),
    }.get(risk_level, risk_level.title())

    risk_color = {"high": "danger", "medium": "warning", "low": "success"}.get(risk_level, "info")
    risk_icon  = {"high": "bi-exclamation-triangle-fill",
                  "medium": "bi-dash-circle-fill",
                  "low": "bi-check-circle-fill"}.get(risk_level, "bi-info-circle")

    # Meaning: purely numeric facts — no filler phrases
    meaning_parts = [
        f"{_vocab('Current', 'Recorded', level)} average: {avg_pct:.1f}%.",
        f"Risk level: {risk_level.upper()} (avg < 40% or ≥2 failures → high; < 60% or 1 failure → medium).",
    ]
    if lr_avg_pred is not None:
        meaning_parts.append(
            f"Trend-projected next-term average: {lr_avg_pred:.1f}% "
            f"across {len(predictions)} subject{'s' if len(predictions) != 1 else ''}."
        )
    if lr_fail > 0:
        meaning_parts.append(f"Subjects projected to fall below pass mark: {lr_fail}.")
    if att_pct > 0:
        meaning_parts.append(f"Attendance: {att_pct:.1f}%.")
    if failed_cnt > 0:
        meaning_parts.append(f"Failed subjects on record: {failed_cnt}.")

    category = {
        "name":    risk_display,
        "color":   risk_color,
        "icon":    risk_icon,
        "meaning": " ".join(meaning_parts),
    }

    # ── 4. Per-subject SHAP + LR reason sentence ─────────────────────────────
    #    Built entirely from: slope, predicted_pct, anomaly_magnitude, r_squared,
    #    shap_trend_contrib, shap_baseline, att_pct (from analytics), failed_cnt
    reason_parts = []

    # Attendance contribution (from analytics att_pct — data, not template text)
    if att_pct < 75:
        reason_parts.append(
            f"Attendance {att_pct:.1f}% (< 75 threshold)."
        )

    # Failing subjects with LR evidence
    failing_preds = [p for p in subject_data if p["is_failing"]]
    if failing_preds:
        details = "; ".join(
            f"{p['subject']}: predicted {p['predicted_pct']:.1f}%, "
            f"slope {p['slope']:+.3f}/term, R²={p['r_squared']:.3f}"
            for p in failing_preds[:3]
        )
        reason_parts.append(f"Below-pass predictions — {details}.")

    # Declining subjects with slope evidence
    dec_preds = [p for p in subject_data if p["trend"] == "declining"]
    if dec_preds:
        worst_dec = min(dec_preds, key=lambda x: x["slope"])
        others    = ", ".join(p["subject"] for p in dec_preds if p["subject"] != worst_dec["subject"])
        detail    = (
            f"{worst_dec['subject']}: slope={worst_dec['slope']:+.3f}/term, "
            f"predicted={worst_dec['predicted_pct']:.1f}%, R²={worst_dec['r_squared']:.3f}"
        )
        if others:
            detail += f"; also {_vocab('going down', 'declining', level)}: {others}"
        reason_parts.append(f"{_vocab('Scores going down', 'Declining trend', level)} — {detail}.")

    # Anomaly drop evidence
    anom_preds = [p for p in subject_data if p["anomaly"] and p["anomaly_direction"] == "drop"]
    if anom_preds:
        worst_anom = max(anom_preds, key=lambda x: x["anomaly_magnitude"])
        reason_parts.append(
            f"Anomaly detected in {worst_anom['subject']}: "
            f"last score deviated {worst_anom['anomaly_magnitude']:.1f}% below the trend line "
            f"(R²={worst_anom['r_squared']:.3f})."
        )

    # SHAP contribution from improving subjects
    imp_preds = [p for p in subject_data if p["trend"] == "improving"]
    if imp_preds:
        best_imp = max(imp_preds, key=lambda x: x["slope"])
        reason_parts.append(
            f"{_vocab('Going up', 'Positive trend', level)}: "
            f"{best_imp['subject']} slope={best_imp['slope']:+.3f}/term, "
            f"predicted={best_imp['predicted_pct']:.1f}%."
        )

    # No issues at all — purely data statement
    if not reason_parts:
        if lr_avg_pred is not None:
            reason_parts.append(
                f"Predicted next-term average: {lr_avg_pred:.1f}%. "
                f"No anomalies or declining trends detected across {len(predictions)} subjects."
            )
        else:
            reason_parts.append(f"Current average: {avg_pct:.1f}%. No exam trend data yet.")

    reason = " ".join(reason_parts)

    # ── 5. Extract SHAP summary from highest-confidence recommendation ────────
    shap_summary = None
    for rec in sorted(recommendations, key=lambda r: r.get("confidence", 0), reverse=True):
        shap_data = rec.get("shap", {})
        if shap_data and shap_data.get("top_driver") not in ("", None, "insufficient_data"):
            shap_summary = {
                "top_driver":     shap_data.get("top_driver", ""),
                "top_direction":  shap_data.get("top_direction", ""),
                "attributions":   list(zip(
                    shap_data.get("feature_names", []),
                    shap_data.get("attributions", [])
                )),
                "explanation":    shap_data.get("explanation", ""),
            }
            break

    # ── 6. Peer comparison from cosine similarity recommendation ─────────────
    peer_comparison = None
    for rec in recommendations:
        if "cosine" in rec.get("algorithm", "").lower() or "similarity" in rec.get("title", "").lower():
            peer_comparison = {
                "message":    rec.get("message", ""),
                "confidence": rec.get("confidence", 0),
            }
            break

    # ── 7. Recommendation cards — direct from services.py, zero modification ─
    #    Strip algorithm names from the title for display (keep message intact)
    recs_display = []
    for rec in recommendations:
        title_clean = rec.get("title", "")
        # Remove parenthetical algorithm labels that may be in the title
        # e.g. "SHAP Analysis: Primary Risk Driver — ..." → keep as-is (it's data)
        recs_display.append({
            "title":      title_clean,
            "message":    rec.get("message", ""),
            "confidence": rec.get("confidence", 0),
            "conf_pct":   round(float(rec.get("confidence", 0)) * 100),
        })

    # ── 8. Study time allocation from LR slope + predicted_pct + SHAP ────────
    #    Minutes ∝ (1 - predicted_pct/100) × max(|slope|, 0.1) × anomaly_weight
    study_allocation = []
    if predictions:
        weights = []
        for p in predictions:
            pred_pct = float(p.get("predicted_percentage", 50))
            slope    = float(p.get("slope", 0))
            amag     = float(p.get("anomaly_magnitude", 0)) if p.get("anomaly") else 0.0
            shap_c   = abs(float(p.get("shap_trend_contrib", 0)))
            w = max((1 - pred_pct / 100) * max(abs(slope), 0.1) + amag / 100 + shap_c / 100, 0.01)
            weights.append((p["subject"], w, pred_pct, slope))

        total_w = sum(x[1] for x in weights) or 1.0
        # Total daily minutes from perf_score (same thresholds as timetable builder)
        if perf_score < 40:   total_min = 240
        elif perf_score < 60: total_min = 180
        elif perf_score < 80: total_min = 120
        else:                 total_min = 90

        for subj, w, pred_pct, slope in sorted(weights, key=lambda x: -x[1]):
            mins = max(round(total_min * w / total_w), 5)
            study_allocation.append({
                "subject":     subj,
                "minutes":     mins,
                "predicted_pct": round(pred_pct, 1),
                "slope":       round(slope, 4),
            })

    # ── 9. Next exam summary — assembled from LR numeric outputs only ─────────
    if lr_avg_pred is not None:
        best_subj  = max(predictions, key=lambda p: p.get("predicted_percentage", 0))
        worst_subj = min(predictions, key=lambda p: p.get("predicted_percentage", 100))
        next_exam = {
            "lr_avg_predicted":  lr_avg_predicted if 'lr_avg_predicted' in dir() else lr_avg_pred,
            "lr_avg_pred":       lr_avg_pred,
            "pass_count":        lr_pass,
            "fail_count":        lr_fail,
            "total_subjects":    len(predictions),
            "best_subject":      best_subj.get("subject", ""),
            "best_pct":          round(float(best_subj.get("predicted_percentage", 0)), 1),
            "worst_subject":     worst_subj.get("subject", ""),
            "worst_pct":         round(float(worst_subj.get("predicted_percentage", 0)), 1),
        }
    else:
        next_exam = {
            "lr_avg_pred": None,
            "pass_count": 0, "fail_count": 0, "total_subjects": 0,
            "best_subject": "", "best_pct": 0,
            "worst_subject": "", "worst_pct": 0,
            "avg_pct_current": avg_pct,
        }

    return {
        "level":               level,
        "category":            category,
        "reason":              reason,
        "subject_data":        subject_data,
        "shap_summary":        shap_summary,
        "next_exam":           next_exam,
        "declining_subjects":  declining_subjects,
        "improving_subjects":  improving_subjects,
        "anomaly_subjects":    anomaly_subjects,
        "stable_subjects":     stable_subjects,
        "peer_comparison":     peer_comparison,
        "recs_display":        recs_display,
        "study_allocation":    study_allocation,
        "avg_pct":             avg_pct,
        "att_pct":             att_pct,
        "failed_count":        failed_cnt,
        "risk_level":          risk_level,
        "gpa":                 gpa,
        "perf_score":          perf_score,
    }




# =====================================================
# STUDY TIMETABLE BUILDER
# =====================================================

def build_study_timetable(student, predictions: list, analytics: dict) -> dict:
    """
    Builds a weekly study timetable derived purely from LR slopes,
    predicted percentages, and SHAP anomaly magnitudes.

    Allocation logic:
    - Total daily study time derived from performance_score.
    - Subject weights: lower predicted_pct + more negative slope + anomaly magnitude.
    - Priority label derived from LR slope thresholds.
    - Critical/worst subjects appear every day; medium subjects 4 days; good 2 days.

    Returns:
        {
          "total_daily_minutes": int,
          "days": [{"day": str, "slots": [...]}, ...],
          "weekly_summary": [{"subject": str, "total_minutes": int,
                              "priority": str, "predicted_pct": float}, ...]
        }
    """
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    perf_score = float(analytics.get("performance_score", 50))

    # ── Total daily minutes from performance_score ────────────────────────────
    if perf_score < 40:
        total_daily_minutes = 240   # 4 hours
    elif perf_score < 60:
        total_daily_minutes = 180   # 3 hours
    elif perf_score < 80:
        total_daily_minutes = 120   # 2 hours
    else:
        total_daily_minutes = 90    # 1.5 hours

    if not predictions:
        return {
            "total_daily_minutes": total_daily_minutes,
            "days": [{"day": d, "slots": []} for d in DAYS],
            "weekly_summary": [],
        }

    # ── Priority label from LR slope ─────────────────────────────────────────
    def _priority(slope: float) -> str:
        if slope < -3:
            return "Critical Focus"
        elif slope < -0.5:
            return "Needs Work"
        elif slope <= 0.5:
            return "Maintain"
        else:
            return "Keep Going"

    # ── Compute weight for each subject ──────────────────────────────────────
    subject_info = []
    for p in predictions:
        pred_pct = float(p.get("predicted_percentage", 50))
        slope = float(p.get("slope", 0))
        anom_mag = float(p.get("anomaly_magnitude", 0)) if p.get("anomaly") else 0.0

        # Weight formula: inverse predicted_pct + negative slope effect + anomaly
        weight = (1 - pred_pct / 100) + max(-slope, 0) / 10 + anom_mag / 100
        weight = max(weight, 0.01)

        priority = _priority(slope)

        subject_info.append({
            "subject": p["subject"],
            "predicted_pct": pred_pct,
            "slope": slope,
            "priority": priority,
            "weight": weight,
        })

    # ── Normalise weights to sum to total_daily_minutes ───────────────────────
    total_weight = sum(s["weight"] for s in subject_info) or 1.0
    for s in subject_info:
        s["daily_minutes"] = max(round(total_daily_minutes * s["weight"] / total_weight), 5)

    # Adjust so totals don't exceed budget (round-robin correction)
    allocated = sum(s["daily_minutes"] for s in subject_info)
    diff = allocated - total_daily_minutes
    if diff != 0 and subject_info:
        # Apply correction to the highest-weight subject
        heaviest = max(subject_info, key=lambda s: s["weight"])
        heaviest["daily_minutes"] = max(heaviest["daily_minutes"] - diff, 5)

    # ── Determine how many days each subject appears ──────────────────────────
    # Critical Focus / Needs Work → every day (6)
    # Maintain → 4 days
    # Keep Going → 2 days
    days_per_subject = {
        "Critical Focus": 6,
        "Needs Work": 6,
        "Maintain": 4,
        "Keep Going": 2,
    }
    for s in subject_info:
        s["n_days"] = days_per_subject[s["priority"]]

    # Sort subjects: worst first (by weight descending) for day assignment
    subject_info.sort(key=lambda s: s["weight"], reverse=True)

    # ── Assign subjects to days ───────────────────────────────────────────────
    # Spread appearances evenly across the week
    day_slots = {d: [] for d in DAYS}

    for s in subject_info:
        n_days = s["n_days"]
        # Choose which days this subject appears: spread evenly
        step = max(len(DAYS) // n_days, 1) if n_days > 0 else len(DAYS)
        chosen_days = DAYS[::step][:n_days]
        # If n_days >= 6, all days
        if n_days >= 6:
            chosen_days = DAYS

        for day in chosen_days:
            day_slots[day].append({
                "subject": s["subject"],
                "minutes": s["daily_minutes"],
                "priority": s["priority"],
                "predicted_pct": round(s["predicted_pct"], 1),
                "slope": round(s["slope"], 4),
            })

    # ── Sort slots within each day by weight desc (worst subjects first) ──────
    for day in DAYS:
        day_slots[day].sort(
            key=lambda slot: next(
                (s["weight"] for s in subject_info if s["subject"] == slot["subject"]), 0
            ),
            reverse=True,
        )

    days_list = [{"day": d, "slots": day_slots[d]} for d in DAYS]

    # ── Weekly summary ────────────────────────────────────────────────────────
    weekly_summary = []
    for s in subject_info:
        total_mins = s["daily_minutes"] * s["n_days"]
        weekly_summary.append({
            "subject": s["subject"],
            "total_minutes": total_mins,
            "priority": s["priority"],
            "predicted_pct": round(s["predicted_pct"], 1),
        })
    weekly_summary.sort(key=lambda x: x["total_minutes"], reverse=True)

    return {
        "total_daily_minutes": total_daily_minutes,
        "days": days_list,
        "weekly_summary": weekly_summary,
    }


# =====================================================
# GRADE / GPA / RISK CONVERTERS
# =====================================================

def percentage_to_grade(percentage: float) -> str:
    p = float(percentage)
    if p >= 90: return "A+"
    if p >= 80: return "A"
    if p >= 70: return "B+"
    if p >= 60: return "B"
    if p >= 50: return "C+"
    if p >= 45: return "C"
    if p >= 40: return "D"
    return "F"


def percentage_to_gpa(percentage: float) -> float:
    p = float(percentage)
    if p >= 90: return 4.0
    if p >= 80: return 3.7
    if p >= 70: return 3.3
    if p >= 60: return 3.0
    if p >= 50: return 2.3
    if p >= 45: return 2.0
    if p >= 40: return 1.0
    return 0.0


def risk_from_percentage(percentage: float, failed_count: int = 0) -> str:
    p = float(percentage)
    if p < 40 or failed_count >= 2:
        return "high"
    if p < 60 or failed_count == 1:
        return "medium"
    return "low"


def _trend_icon(trend: str) -> str:
    if trend == "improving": return "↑"
    if trend == "declining": return "↓"
    return "→"


def _confidence_from_trend_and_data(trend: str, data_points: int) -> int:
    """Derive a display confidence % from trend + number of data points."""
    base = {"improving": 82, "declining": 78, "stable": 70}.get(trend, 70)
    bonus = min(data_points * 3, 15)
    return min(base + bonus, 95)


# =====================================================
# PANEL 1 — SUBJECT-WISE PREDICTION TABLE
# =====================================================

def build_subject_prediction_table(predictions: list) -> list:
    """
    Enrich predict_future_marks() output for the Subject-Wise Prediction Table.
    Returns rows sorted by predicted_pct descending.
    """
    if not predictions:
        return []

    rows = []
    for pred in predictions:
        past = pred.get("past_percentages", [])
        predicted = float(pred.get("predicted_percentage", 0))
        trend = pred.get("trend", "stable")

        prev_pct = round(float(past[-2]), 1) if len(past) >= 2 else None
        curr_pct = round(float(past[-1]), 1) if len(past) >= 1 else None

        rows.append({
            "subject":          pred.get("subject", ""),
            "previous_term_pct": prev_pct,
            "current_term_pct":  curr_pct,
            "predicted_pct":     round(predicted, 1),
            "predicted_grade":   percentage_to_grade(predicted),
            "predicted_gpa":     percentage_to_gpa(predicted),
            "trend":             trend,
            "trend_icon":        _trend_icon(trend),
            "confidence_pct":    _confidence_from_trend_and_data(trend, len(past)),
        })

    rows.sort(key=lambda r: r["predicted_pct"], reverse=True)
    return rows



# PANEL 2 — TERM-WISE FORECAST TABLE


def build_term_forecast(predictions: list, analytics: dict) -> list:
    """
    Build a term-by-term forecast table.
    Past terms are reconstructed from past_percentages; last row is predicted.
    """
    if not predictions:
        return []

    # Find max number of past terms across all subjects
    max_terms = max((len(p.get("past_percentages", [])) for p in predictions), default=0)
    if max_terms == 0:
        return []

    rows = []

    for term_idx in range(max_terms):
        term_pcts = []
        pass_count = 0
        fail_count = 0

        for pred in predictions:
            past = pred.get("past_percentages", [])
            if term_idx < len(past):
                pct = float(past[term_idx])
                term_pcts.append(pct)
                if pct >= 40:
                    pass_count += 1
                else:
                    fail_count += 1

        if not term_pcts:
            continue

        avg_pct = round(sum(term_pcts) / len(term_pcts), 2)
        rows.append({
            "term_label":    f"Term {term_idx + 1}",
            "is_predicted":  False,
            "avg_percentage": avg_pct,
            "avg_gpa":       round(percentage_to_gpa(avg_pct), 2),
            "pass_count":    pass_count,
            "fail_count":    fail_count,
            "risk_level":    risk_from_percentage(avg_pct, fail_count),
        })

    # Predicted next term row
    pred_pcts = [float(p.get("predicted_percentage", 0)) for p in predictions]
    if pred_pcts:
        avg_pred = round(sum(pred_pcts) / len(pred_pcts), 2)
        pred_pass = sum(1 for p in pred_pcts if p >= 40)
        pred_fail = len(pred_pcts) - pred_pass
        rows.append({
            "term_label":    "Predicted Next",
            "is_predicted":  True,
            "avg_percentage": avg_pred,
            "avg_gpa":       round(percentage_to_gpa(avg_pred), 2),
            "pass_count":    pred_pass,
            "fail_count":    pred_fail,
            "risk_level":    risk_from_percentage(avg_pred, pred_fail),
        })

    return rows



# PANEL 3 — SUBJECT RANKING PANEL


def build_subject_ranking(predictions: list) -> dict:
    """
    Sort existing predictions to identify strongest and weakest subjects.
    No new algorithm — pure sort on predicted_percentage.

    Strongest  = top 3 by predicted_pct (genuinely high performers)
    Needs Attention = subjects that are EITHER predicted < 40 (failing)
                      OR have a declining trend AND predicted < 60.
                      Falls back to bottom 3 only if no genuinely weak subjects found.

    Total subjects split: pass_count (predicted >= 40) vs fail_count (predicted < 40).
    Each item includes term-to-term arrow showing direction of travel.
    """
    if not predictions:
        return {
            "strongest": [], "needs_attention": [],
            "total_subjects": 0, "pass_count": 0, "fail_count": 0,
        }

    total = len(predictions)
    pass_count = sum(1 for p in predictions if float(p.get("predicted_percentage", 0)) >= 40)
    fail_count = total - pass_count

    items = []
    for p in predictions:
        past = p.get("past_percentages", [])
        pred_pct = round(float(p.get("predicted_percentage", 0)), 1)
        trend = p.get("trend", "stable")

        # Build term arrows: e.g. [62.0, 71.0, →predicted 78.0]
        term_arrows = []
        for i, pct in enumerate(past):
            term_arrows.append({"label": f"T{i+1}", "pct": round(float(pct), 1)})
        term_arrows.append({"label": "Next", "pct": pred_pct, "is_predicted": True})

        # Direction arrow between consecutive terms
        direction_arrows = []
        all_pcts = [t["pct"] for t in term_arrows]
        for i in range(len(all_pcts) - 1):
            diff = all_pcts[i+1] - all_pcts[i]
            if diff > 2:
                direction_arrows.append("↑")
            elif diff < -2:
                direction_arrows.append("↓")
            else:
                direction_arrows.append("→")

        items.append({
            "subject":        p.get("subject", ""),
            "predicted_pct":  pred_pct,
            "grade":          percentage_to_grade(pred_pct),
            "trend":          trend,
            "trend_icon":     _trend_icon(trend),
            "term_arrows":    term_arrows,
            "dir_arrows":     direction_arrows,
            "past_count":     len(past),
        })

    sorted_desc = sorted(items, key=lambda x: x["predicted_pct"], reverse=True)

    # ── Categorize subjects properly ──────────────────────────────────
    # "Be Careful / Highly Needs Attention": ANY decrease in % from any term to next
    # "Constant": increasing by only 1-2% per term
    # "Strongest": clearly improving (>2% per term increase consistently)
    # "Needs Attention": declining trend OR predicted < 40

    def _classify_subject(item):
        """
        Returns category string based on term-to-term movement.
        Uses actual past_percentages deltas, not just the trend label.
        """
        past = [t["pct"] for t in item["term_arrows"] if not t.get("is_predicted")]
        pred = item["predicted_pct"]
        all_pcts = past + [pred]

        if len(all_pcts) < 2:
            # Only one data point — use predicted vs pass mark
            if pred < 40:
                return "highly_needs_attention"
            if pred >= 75:
                return "strongest"
            return "constant"

        # Check every consecutive pair
        deltas = [all_pcts[i+1] - all_pcts[i] for i in range(len(all_pcts)-1)]
        any_decrease = any(d < 0 for d in deltas)  # ANY drop, even 0.1%
        avg_delta = sum(deltas) / len(deltas)

        if pred < 40:
            return "highly_needs_attention"
        if any_decrease:
            return "be_careful"
        if avg_delta <= 2:
            return "constant"
        return "strongest"

    for item in items:
        item["category"] = _classify_subject(item)

    # Needs attention = highly_needs_attention + be_careful
    needs_attention_items = [i for i in items if i["category"] in ("highly_needs_attention", "be_careful")]
    needs_attention_items = sorted(needs_attention_items, key=lambda x: x["predicted_pct"])[:3]

    # Strongest = category "strongest" sorted desc
    strongest_items = [i for i in sorted_desc if i["category"] == "strongest"][:3]
    # If no "strongest", fall back to top 3 by predicted_pct
    if not strongest_items:
        strongest_items = sorted_desc[:3]

    return {
        "strongest":       strongest_items,
        "needs_attention": needs_attention_items,
        "total_subjects":  total,
        "pass_count":      pass_count,
        "fail_count":      fail_count,
    }



# PANEL 4 — PERFORMANCE INSIGHTS

def build_performance_insights(predictions: list, recommendations: list) -> list:
    """
    Derives insight sentences purely from LR prediction outputs and
    recommendation messages produced by the algorithm pipeline.
    No hardcoded text — every sentence is assembled from actual data values.
    """
    if not predictions and not recommendations:
        return []

    insights = []

    # From LR predictions: use subject name, slope, predicted_pct, trend
    for p in predictions:
        subj  = p.get("subject", "")
        trend = p.get("trend", "stable")
        pred  = float(p.get("predicted_percentage", 0))
        slope = float(p.get("slope", 0))
        anomaly = p.get("anomaly", False)
        anom_dir = p.get("anomaly_direction", None)
        anom_mag = float(p.get("anomaly_magnitude", 0))

        if anomaly and anom_dir == "drop":
            insights.append(
                f"{subj}: anomaly detected — score dropped {anom_mag:.1f} pts "
                f"below the predicted trend line."
            )
        elif anomaly and anom_dir == "spike":
            insights.append(
                f"{subj}: unexpected spike of {anom_mag:.1f} pts above trend. "
                f"Verify if this reflects consistent improvement."
            )
        elif trend == "improving" and slope > 0:
            insights.append(
                f"{subj} — LR slope: {slope:+.2f}/term. "
                f"Predicted next-term: {pred:.1f}%."
            )
        elif trend == "declining" and slope < 0:
            insights.append(
                f"{subj} — LR slope: {slope:+.2f}/term (declining). "
                f"Predicted next-term: {pred:.1f}%. Needs attention."
            )
        elif pred < 40:
            insights.append(
                f"{subj} — predicted score {pred:.1f}% is below pass mark (40%)."
            )

    # From recommendations: use algorithm field and title (algorithm-generated)
    for rec in recommendations[:3]:
        alg   = rec.get("algorithm", "")
        title = rec.get("title", "")
        conf  = float(rec.get("confidence", 0))
        if alg and title:
            insights.append(
                f"{title} [{alg}, confidence: {conf:.0%}]."
            )

    # Deduplicate
    seen = set()
    unique = []
    for ins in insights:
        if ins not in seen:
            seen.add(ins)
            unique.append(ins)

    return unique[:8]



# PANEL 5 — STUDENT FUTURE OUTLOOK


def build_student_outlook(predictions: list, analytics: dict) -> dict:
    """
    Aggregate existing prediction outputs into a single outlook summary.
    """
    default = {
        "predicted_avg_pct":   0,
        "predicted_gpa":       0.0,
        "predicted_grade":     "N/A",
        "predicted_risk_level": "N/A",
        "predicted_pass_count": 0,
        "predicted_fail_count": 0,
        "attendance_impact":   "N/A",
        "chart_data": {
            "labels": ["Predicted Pass", "Predicted Fail"],
            "values": [0, 0],
            "colors": ["#4ade80", "#f87171"],
        },
    }

    if not predictions:
        return default

    pred_pcts = [float(p.get("predicted_percentage", 0)) for p in predictions]
    avg_pct   = round(sum(pred_pcts) / len(pred_pcts), 2)
    pass_count = sum(1 for p in pred_pcts if p >= 40)
    fail_count = len(pred_pcts) - pass_count

    att_pct = float(analytics.get("attendance_percentage", 0))
    if att_pct >= 75:
        att_impact = "Positive"
    elif att_pct < 60:
        att_impact = "At Risk"
    else:
        att_impact = "Neutral"

    return {
        "predicted_avg_pct":    avg_pct,
        "predicted_gpa":        percentage_to_gpa(avg_pct),
        "predicted_grade":      percentage_to_grade(avg_pct),
        "predicted_risk_level": risk_from_percentage(avg_pct, fail_count),
        "predicted_pass_count": pass_count,
        "predicted_fail_count": fail_count,
        "attendance_impact":    att_impact,
        "chart_data": {
            "labels": ["Predicted Pass", "Predicted Fail"],
            "values": [pass_count, fail_count],
            "colors": ["#4ade80", "#f87171"],
        },
    }



# PANEL 6 — SUBJECT TIMELINE VIEW


def build_subject_timeline(predictions: list) -> list:
    """
    Build a per-subject timeline: past terms → predicted next.
    """
    if not predictions:
        return []

    result = []
    for pred in predictions:
        past  = pred.get("past_percentages", [])
        trend = pred.get("trend", "stable")

        timeline = [
            {"label": f"Term {i + 1}", "pct": round(float(pct), 1), "is_predicted": False}
            for i, pct in enumerate(past)
        ]
        timeline.append({
            "label":        "Predicted",
            "pct":          round(float(pred.get("predicted_percentage", 0)), 1),
            "is_predicted": True,
        })

        result.append({
            "subject":    pred.get("subject", ""),
            "timeline":   timeline,
            "trend":      trend,
            "trend_icon": _trend_icon(trend),
        })

    return result


# TEACHER VIEW HELPER


def build_teacher_summary(all_data: list, staff_profile=None) -> dict:
    """
    Aggregate run_analytics_for_all_students() output into a teacher-friendly summary.
    If staff_profile is provided, filters to only subjects that teacher is assigned to.
    Calls predict_future_marks() per student — no new algorithm, aggregation only.
    """
    from academics.models import TeacherSubjectAssignment

    empty = {
        "subject_summary":        [],
        "at_risk_subjects":       [],
        "most_improved_subjects": [],
        "declining_subjects":     [],
        "interventions":          [],
        "subject_teacher_map":    {},
        "declining_teacher_map":  {},
        "risk_distribution": {
            "labels": ["High Risk", "Medium Risk", "Low Risk"],
            "values": [0, 0, 0],
        },
        "total_students":    0,
        "high_risk_count":   0,
        "medium_risk_count": 0,
        "low_risk_count":    0,
        "is_filtered":       staff_profile is not None,
        "assigned_subjects": [],
    }

    if not all_data:
        return empty

    # If staff_profile given, get their assigned subject names
    assigned_subject_names = set()
    assigned_subject_details = []  # [{subject, class, section}]
    if staff_profile:
        assignments = TeacherSubjectAssignment.objects.filter(
            teacher=staff_profile
        ).select_related(
            "class_subject__subject", "class_subject__class_obj", "section"
        )
        for a in assignments:
            name = a.class_subject.subject.name
            assigned_subject_names.add(name)
            assigned_subject_details.append({
                "subject":   name,
                "class_obj": a.class_subject.class_obj.name,
                "section":   a.section.name,
            })

    # Build subject→teacher map for all subjects
    subject_teacher_map = {}
    try:
        all_assignments = TeacherSubjectAssignment.objects.select_related(
            "teacher__user", "class_subject__subject",
            "class_subject__class_obj", "section"
        ).all()
        for a in all_assignments:
            subj = a.class_subject.subject.name
            cls  = a.class_subject.class_obj.name
            sec  = a.section.name
            key  = f"{subj}|{cls}|{sec}"
            teacher_name = a.teacher.user.get_full_name() or a.teacher.user.username
            subject_teacher_map[key] = teacher_name
            # Also store by subject name alone for quick lookup
            if subj not in subject_teacher_map:
                subject_teacher_map[subj] = teacher_name
    except Exception:
        pass

    subject_data = {}
    # Per-subject student tracking for "Subjects Needing Attention" panel
    subject_students = {}   # subject → list of {name, class, section, roll, avg_pct, student_id, pred_pct, trend}
    high_risk = medium_risk = low_risk = 0

    for item in all_data:
        student   = item.get("student")
        analytics = item.get("analytics", {})

        risk = analytics.get("risk_level", "low")
        if risk == "high":     high_risk   += 1
        elif risk == "medium": medium_risk += 1
        else:                  low_risk    += 1

        if student is None:
            continue

        try:
            preds = predict_future_marks(student)
        except Exception:
            preds = []

        # Attendance for this student
        att_pct = float(analytics.get("attendance_percentage", 0))

        # Student display info
        try:
            cls_name = student.section.class_obj.name
            sec_name = student.section.name
        except Exception:
            cls_name = "—"
            sec_name = "—"
        try:
            stu_name = student.user.get_full_name() or student.user.username
        except Exception:
            stu_name = str(student)

        for pred in preds:
            subj  = pred.get("subject", "Unknown")
            pct   = float(pred.get("predicted_percentage", 0))
            trend = pred.get("trend", "stable")

            # Filter to assigned subjects if staff_profile given
            if staff_profile and subj not in assigned_subject_names:
                continue

            if subj not in subject_data:
                subject_data[subj] = {
                    "pcts": [], "improving": 0, "declining": 0,
                    "stable": 0, "at_risk": 0, "student_count": 0,
                    "att_pcts": [],
                }

            subject_data[subj]["pcts"].append(pct)
            subject_data[subj]["student_count"] += 1
            subject_data[subj][trend] = subject_data[subj].get(trend, 0) + 1
            subject_data[subj]["att_pcts"].append(att_pct)
            if pct < 40:
                subject_data[subj]["at_risk"] += 1

            # Track students who are at-risk OR declining for this subject
            if pct < 60 or trend == "declining":
                if subj not in subject_students:
                    subject_students[subj] = []
                subject_students[subj].append({
                    "name":       stu_name,
                    "class":      cls_name,
                    "section":    sec_name,
                    "roll":       student.roll_number,
                    "avg_pct":    round(pct, 1),
                    "student_id": student.id,
                    "trend":      trend,
                    "risk":       risk,
                })

    subject_summary = []
    for subj, data in subject_data.items():
        avg_pct      = round(sum(data["pcts"]) / len(data["pcts"]), 2) if data["pcts"] else 0
        avg_att      = round(sum(data["att_pcts"]) / len(data["att_pcts"]), 1) if data["att_pcts"] else 0
        teacher_name = subject_teacher_map.get(subj, "—")
        # Attach per-subject at-risk students directly to each row
        stu_list = subject_students.get(subj, [])
        subject_summary.append({
            "subject":           subj,
            "avg_predicted_pct": avg_pct,
            "student_count":     data["student_count"],
            "improving_count":   data.get("improving", 0),
            "declining_count":   data.get("declining", 0),
            "stable_count":      data.get("stable", 0),
            "at_risk_count":     data.get("at_risk", 0),
            "avg_attendance":    avg_att,
            "teacher":           teacher_name,
            "at_risk_students":  stu_list,   # list of dicts ready for template
        })

    subject_summary.sort(key=lambda x: x["avg_predicted_pct"])

    at_risk_subjects = [s["subject"] for s in subject_summary if s["avg_predicted_pct"] < 40]
    most_improved    = sorted(subject_summary, key=lambda x: x["improving_count"], reverse=True)[:3]
    # at_risk = subjects where declining_count > improving_count (genuinely declining)
    declining_subjs  = [s for s in subject_summary if s["declining_count"] > s["improving_count"]]

    # Declining teacher map: subject → teacher name
    declining_teacher_map = {
        s["subject"]: subject_teacher_map.get(s["subject"], "—")
        for s in declining_subjs
    }

    # Interventions — derived from algorithm outputs only (LR slopes + predicted pcts)
    interventions = []
    if at_risk_subjects:
        worst_pcts = {
            s["subject"]: s["avg_predicted_pct"]
            for s in subject_summary if s["subject"] in at_risk_subjects
        }
        worst_text = ", ".join(
            f"{subj} ({pct:.1f}%)"
            for subj, pct in sorted(worst_pcts.items(), key=lambda x: x[1])[:3]
        )
        interventions.append(
            f"LR predicts below-pass scores in: {worst_text}. "
            f"Remedial intervention required before next assessment."
        )
    if declining_subjs:
        slope_text = ", ".join(
            f"{s['subject']} (avg predicted: {s['avg_predicted_pct']:.1f}%, "
            f"declining: {s['declining_count']} students)"
            for s in declining_subjs[:3]
        )
        interventions.append(
            f"LR slope is negative for: {slope_text}. "
            f"Review contributing factors identified by SHAP attribution."
        )
    low_att_subjects = [s for s in subject_summary if s["avg_attendance"] < 70]
    if low_att_subjects:
        att_text = ", ".join(
            f"{s['subject']} ({s['avg_attendance']:.0f}% avg att.)"
            for s in low_att_subjects[:2]
        )
        interventions.append(
            f"Low class attendance in: {att_text}. "
            f"SHAP attribution analysis flags attendance as a negative driver "
            f"for predicted scores in these subjects."
        )
    if high_risk > 0:
        interventions.append(
            f"{high_risk} student(s) classified as high-risk by the prediction model "
            f"(avg percentage < 40% or ≥2 failed subjects). "
            f"SHAP explanations available on each student's detail page."
        )
    if most_improved and most_improved[0]["improving_count"] > 0:
        best = most_improved[0]
        interventions.append(
            f"LR shows positive slope for {best['student_count']} students in "
            f"{best['subject']} ({best['improving_count']} improving). "
            f"Avg predicted: {best['avg_predicted_pct']:.1f}%. Reinforce this momentum."
        )
    if not interventions:
        interventions.append(
            "LR prediction model shows stable or improving slopes across all subjects. "
            "No immediate intervention required based on current trend analysis."
        )

    total = len(all_data)

    # Build students_by_risk for teacher popup
    students_by_risk = {"high": [], "medium": [], "low": []}
    # Per-class breakdown for drill-down in Subjects Needing Attention
    students_by_class = {}
    for item in all_data:
        student   = item.get("student")
        analytics = item.get("analytics", {})
        if student is None:
            continue
        risk = analytics.get("risk_level", "low")
        try:
            cls_name = student.section.class_obj.name
            sec_name = student.section.name
        except Exception:
            cls_name = "—"
            sec_name = "—"
        try:
            name = student.user.get_full_name() or student.user.username
        except Exception:
            name = str(student)
        entry = {
            "name":    name,
            "class":   cls_name,
            "section": sec_name,
            "roll":    student.roll_number,
            "avg_pct": analytics.get("average_percentage", 0),
            "student_id": student.id,
            "risk":    risk,
        }
        if risk in students_by_risk:
            students_by_risk[risk].append(entry)
        if cls_name not in students_by_class:
            students_by_class[cls_name] = {"high": [], "medium": [], "low": [], "all": []}
        students_by_class[cls_name][risk].append(entry)
        students_by_class[cls_name]["all"].append(entry)

    for cls_name in students_by_class:
        for bucket in ("high", "medium", "low", "all"):
            students_by_class[cls_name][bucket].sort(key=lambda x: x["avg_pct"])

    # Sort per-subject student lists: high-risk first, then by predicted pct ascending
    for subj in subject_students:
        subject_students[subj].sort(key=lambda x: (0 if x["risk"] == "high" else 1, x["avg_pct"]))

    return {
        "subject_summary":        subject_summary,
        "at_risk_subjects":       at_risk_subjects,
        "most_improved_subjects": [s["subject"] for s in most_improved],
        "declining_subjects":     [s["subject"] for s in declining_subjs],
        "declining_teacher_map":  declining_teacher_map,
        "subject_teacher_map":    subject_teacher_map,
        "interventions":          interventions[:5],
        "risk_distribution": {
            "labels": ["High Risk", "Medium Risk", "Low Risk"],
            "values": [high_risk, medium_risk, low_risk],
        },
        "students_by_risk":    students_by_risk,
        "subject_students":    subject_students,   # per-subject at-risk student list
        "students_by_class":   students_by_class,  # per-class risk buckets for drill-down
        "total_students":      total,
        "high_risk_count":     high_risk,
        "medium_risk_count":   medium_risk,
        "low_risk_count":      low_risk,
        "is_filtered":         staff_profile is not None,
        "assigned_subjects":   assigned_subject_details,
    }


# =====================================================
# PRINCIPAL VIEW HELPER
# =====================================================

def build_principal_summary(all_data: list) -> dict:
    """
    Aggregate run_analytics_for_all_students() output into a principal-friendly
    school-wide summary. Groups students by class.
    """
    empty = {
        "school_stats": {
            "total_students":    0,
            "avg_predicted_pct": 0,
            "avg_predicted_gpa": 0,
            "high_risk_count":   0,
            "medium_risk_count": 0,
            "low_risk_count":    0,
        },
        "class_summary":           [],
        "top_improving_classes":   [],
        "needs_attention_classes": [],
        "gpa_chart": {"labels": [], "current_gpas": [], "predicted_gpas": []},
        "risk_chart": {"labels": [], "high": [], "medium": [], "low": []},
    }

    if not all_data:
        return empty

    # Group by class
    class_data = {}

    for item in all_data:
        student   = item.get("student")
        analytics = item.get("analytics", {})

        if student is None:
            continue

        try:
            class_name = student.section.class_obj.name
        except Exception:
            class_name = "Unknown"

        if class_name not in class_data:
            class_data[class_name] = {
                "current_pcts": [], "predicted_pcts": [],
                "high": 0, "medium": 0, "low": 0,
            }

        current_pct = float(analytics.get("average_percentage", 0))
        class_data[class_name]["current_pcts"].append(current_pct)

        risk = analytics.get("risk_level", "low")
        class_data[class_name][risk] = class_data[class_name].get(risk, 0) + 1

        # Get predicted avg for this student
        try:
            preds = predict_future_marks(student)
            if preds:
                pred_avg = sum(float(p.get("predicted_percentage", 0)) for p in preds) / len(preds)
                class_data[class_name]["predicted_pcts"].append(pred_avg)
        except Exception:
            pass

    class_summary = []
    for cls, data in class_data.items():
        curr_pcts = data["current_pcts"]
        pred_pcts = data["predicted_pcts"]

        avg_curr = round(sum(curr_pcts) / len(curr_pcts), 2) if curr_pcts else 0
        avg_pred = round(sum(pred_pcts) / len(pred_pcts), 2) if pred_pcts else avg_curr

        if avg_pred > avg_curr + 2:
            trend = "improving"
        elif avg_pred < avg_curr - 2:
            trend = "declining"
        else:
            trend = "stable"

        class_summary.append({
            "class_name":        cls,
            "student_count":     len(curr_pcts),
            "avg_current_pct":   avg_curr,
            "avg_predicted_pct": avg_pred,
            "avg_predicted_gpa": round(percentage_to_gpa(avg_pred), 2),
            "high_risk_count":   data.get("high", 0),
            "medium_risk_count": data.get("medium", 0),
            "low_risk_count":    data.get("low", 0),
            "trend":             trend,
        })

    class_summary.sort(key=lambda x: x["avg_predicted_pct"])

    # School-wide stats
    all_curr  = [c["avg_current_pct"]   for c in class_summary]
    all_pred  = [c["avg_predicted_pct"] for c in class_summary]
    total_stu = sum(c["student_count"]  for c in class_summary)
    total_high   = sum(c["high_risk_count"]   for c in class_summary)
    total_medium = sum(c["medium_risk_count"] for c in class_summary)
    total_low    = sum(c["low_risk_count"]    for c in class_summary)

    school_avg_pred = round(sum(all_pred) / len(all_pred), 2) if all_pred else 0

    # Top improving: biggest positive delta
    improving_sorted = sorted(
        class_summary,
        key=lambda x: x["avg_predicted_pct"] - x["avg_current_pct"],
        reverse=True
    )
    top_improving = [c["class_name"] for c in improving_sorted[:3]
                     if c["avg_predicted_pct"] > c["avg_current_pct"]]

    labels = [c["class_name"] for c in class_summary]

    # Build declining subject → teacher map for principal view
    declining_subject_teacher = {}
    try:
        from academics.models import TeacherSubjectAssignment
        assignments = TeacherSubjectAssignment.objects.select_related(
            "teacher__user", "class_subject__subject",
            "class_subject__class_obj", "section"
        ).all()
        for a in assignments:
            subj      = a.class_subject.subject.name
            cls_name  = a.class_subject.class_obj.name
            sec_name  = a.section.name
            t_name    = a.teacher.user.get_full_name() or a.teacher.user.username
            key = f"{subj}|{cls_name}"
            if key not in declining_subject_teacher:
                declining_subject_teacher[key] = {
                    "teacher": t_name,
                    "subject": subj,
                    "class":   cls_name,
                    "section": sec_name,
                }
    except Exception:
        pass

    # Collect declining subjects across all classes with teacher info
    declining_with_teacher = []
    for item in all_data:
        student = item.get("student")
        if student is None:
            continue
        try:
            cls_name = student.section.class_obj.name
            preds = predict_future_marks(student)
            for pred in preds:
                if pred.get("trend") == "declining":
                    subj = pred.get("subject", "")
                    key  = f"{subj}|{cls_name}"
                    info = declining_subject_teacher.get(key, {})
                    entry = {
                        "subject": subj,
                        "class":   cls_name,
                        "teacher": info.get("teacher", "—"),
                        "section": info.get("section", "—"),
                        "predicted_pct": round(float(pred.get("predicted_percentage", 0)), 1),
                    }
                    if not any(d["subject"] == subj and d["class"] == cls_name
                               for d in declining_with_teacher):
                        declining_with_teacher.append(entry)
        except Exception:
            pass

    declining_with_teacher.sort(key=lambda x: x["predicted_pct"])

    # Build needs_attention AFTER declining_with_teacher is ready
    needs_attention = []
    for c in class_summary:
        declining_subs_for_class = [
            d for d in declining_with_teacher if d["class"] == c["class_name"]
        ]
        if c["avg_predicted_pct"] < 50 or c["high_risk_count"] > 0 or declining_subs_for_class:
            sub_names = ", ".join(d["subject"] for d in declining_subs_for_class[:3])
            needs_attention.append({
                "class_name":         c["class_name"],
                "avg_predicted_pct":  c["avg_predicted_pct"],
                "high_risk_count":    c["high_risk_count"],
                "declining_subjects": sub_names or "Overall performance low",
                "note": (
                    f"{c['high_risk_count']} high risk student(s)" if c["high_risk_count"] > 0
                    else f"Avg predicted: {c['avg_predicted_pct']}%"
                ),
            })

    # Fix class trend: classes with high-risk students cannot be "improving"
    for c in class_summary:
        if c["high_risk_count"] > 0 and c["trend"] == "improving":
            c["trend"] = "stable"
        if c["student_count"] > 0:
            high_ratio = c["high_risk_count"] / c["student_count"]
            if high_ratio >= 0.5:
                c["trend"] = "declining"

    # Recompute top_improving after trend fix
    top_improving = [
        c["class_name"] for c in sorted(
            class_summary,
            key=lambda x: x["avg_predicted_pct"] - x["avg_current_pct"],
            reverse=True
        )
        if c["avg_predicted_pct"] > c["avg_current_pct"]
        and c["trend"] == "improving"
        and c["high_risk_count"] == 0
    ][:3]

    # Build students_by_risk for principal popup
    students_by_risk = {"high": [], "medium": [], "low": []}
    # Also build students_by_class for per-class drill-down
    students_by_class = {}
    for item in all_data:
        student   = item.get("student")
        analytics = item.get("analytics", {})
        if student is None:
            continue
        risk = analytics.get("risk_level", "low")
        try:
            cls_name = student.section.class_obj.name
            sec_name = student.section.name
        except Exception:
            cls_name = "—"
            sec_name = "—"
        try:
            name = student.user.get_full_name() or student.user.username
        except Exception:
            name = str(student)
        entry = {
            "name":       name,
            "class":      cls_name,
            "section":    sec_name,
            "roll":       student.roll_number,
            "avg_pct":    analytics.get("average_percentage", 0),
            "student_id": student.id,
            "risk":       risk,
        }
        if risk in students_by_risk:
            students_by_risk[risk].append(entry)
        # Group by class
        if cls_name not in students_by_class:
            students_by_class[cls_name] = {"high": [], "medium": [], "low": [], "all": []}
        students_by_class[cls_name][risk].append(entry)
        students_by_class[cls_name]["all"].append(entry)

    # Sort each class bucket by avg_pct ascending (worst first)
    for cls_name in students_by_class:
        for bucket in ("high", "medium", "low", "all"):
            students_by_class[cls_name][bucket].sort(key=lambda x: x["avg_pct"])

    return {
        "school_stats": {
            "total_students":    total_stu,
            "avg_predicted_pct": school_avg_pred,
            "avg_predicted_gpa": round(percentage_to_gpa(school_avg_pred), 2),
            "high_risk_count":   total_high,
            "medium_risk_count": total_medium,
            "low_risk_count":    total_low,
        },
        "class_summary":           class_summary,
        "top_improving_classes":   top_improving,
        "needs_attention_classes": needs_attention,
        "declining_with_teacher":  declining_with_teacher,
        "students_by_risk":        students_by_risk,
        "students_by_class":       students_by_class,
        "gpa_chart": {
            "labels":         labels,
            "current_gpas":   [round(percentage_to_gpa(c["avg_current_pct"]), 2)   for c in class_summary],
            "predicted_gpas": [round(percentage_to_gpa(c["avg_predicted_pct"]), 2) for c in class_summary],
        },
        "risk_chart": {
            "labels": labels,
            "high":   [c["high_risk_count"]   for c in class_summary],
            "medium": [c["medium_risk_count"] for c in class_summary],
            "low":    [c["low_risk_count"]    for c in class_summary],
        },
    }


# =====================================================
# PRINCIPAL — SUBJECT-WISE TEACHER ADVICE
# =====================================================

def build_subject_teacher_advice(all_data: list) -> list:
    """
    For the Principal view: builds a subject-wise list of recommendations
    directed at each subject's teacher.  Written in plain professional language
    — no algorithm or tool names.  Principal sees which teacher to focus on
    and what that teacher should do.

    Returns a list of dicts, one per subject, sorted by urgency (worst first).
    Each dict:
      subject, teacher, avg_predicted_pct, student_count,
      declining_count, at_risk_count, avg_attendance,
      principal_advice (str), urgency (high/medium/low),
      key_issues (list of short strings)
    """
    if not all_data:
        return []

    try:
        from academics.models import TeacherSubjectAssignment
    except ImportError:
        return []

    # Build subject → teacher map
    subject_teacher_map = {}
    try:
        for a in TeacherSubjectAssignment.objects.select_related(
            "teacher__user", "class_subject__subject", "class_subject__class_obj", "section"
        ).all():
            subj = a.class_subject.subject.name
            t_name = a.teacher.user.get_full_name() or a.teacher.user.username
            if subj not in subject_teacher_map:
                subject_teacher_map[subj] = t_name
    except Exception:
        pass

    # Aggregate subject stats
    subject_data = {}
    for item in all_data:
        student   = item.get("student")
        analytics = item.get("analytics", {})
        if student is None:
            continue
        att_pct = float(analytics.get("attendance_percentage", 0))
        try:
            preds = predict_future_marks(student)
        except Exception:
            preds = []
        for pred in preds:
            subj  = pred.get("subject", "Unknown")
            pct   = float(pred.get("predicted_percentage", 0))
            trend = pred.get("trend", "stable")
            if subj not in subject_data:
                subject_data[subj] = {
                    "pcts": [], "declining": 0, "improving": 0, "stable": 0,
                    "at_risk": 0, "att_pcts": [], "student_count": 0,
                }
            subject_data[subj]["pcts"].append(pct)
            subject_data[subj]["student_count"] += 1
            subject_data[subj]["att_pcts"].append(att_pct)
            subject_data[subj][trend] = subject_data[subj].get(trend, 0) + 1
            if pct < 40:
                subject_data[subj]["at_risk"] += 1

    advice_list = []
    for subj, data in subject_data.items():
        avg_pct   = round(sum(data["pcts"]) / len(data["pcts"]), 2) if data["pcts"] else 0
        avg_att   = round(sum(data["att_pcts"]) / len(data["att_pcts"]), 1) if data["att_pcts"] else 0
        teacher   = subject_teacher_map.get(subj, "Unassigned")
        n         = data["student_count"]
        declining = data.get("declining", 0)
        improving = data.get("improving", 0)
        at_risk   = data.get("at_risk", 0)

        key_issues = []
        advice_parts = []

        # Urgency logic
        if avg_pct < 40 or at_risk >= max(1, n * 0.4):
            urgency = "high"
        elif avg_pct < 60 or declining > improving:
            urgency = "medium"
        else:
            urgency = "low"

        # Build teacher-directed advice
        if teacher == "Unassigned":
            advice_parts.append(
                f"No teacher is currently assigned to {subj}. "
                "Assign a qualified teacher immediately so students get proper guidance."
            )
            key_issues.append("No teacher assigned")
        else:
            if avg_pct < 40:
                advice_parts.append(
                    f"{teacher} should hold extra support classes for {subj} as soon as possible. "
                    f"The class average is only {avg_pct}%, which means most students are not passing. "
                    "The teacher should go back to the basics, make sure every student understands "
                    "the core ideas before moving to harder topics."
                )
                key_issues.append(f"Class average {avg_pct}% — below pass mark")
            elif avg_pct < 60:
                advice_parts.append(
                    f"{teacher} needs to check which topics students find most difficult in {subj}. "
                    f"With an average of {avg_pct}%, many students are struggling. "
                    "The teacher should use more examples, give practice exercises after each lesson, "
                    "and check understanding regularly."
                )
                key_issues.append(f"Class average {avg_pct}% — room for improvement")

            if declining > n * 0.3:
                advice_parts.append(
                    f"{declining} out of {n} students in {subj} are getting lower marks each term. "
                    f"{teacher} should find out what changed — whether a topic was harder, "
                    "the pace was too fast, or students need more practice. "
                    "Going back and reteaching those sections can stop this decline."
                )
                key_issues.append(f"{declining} students declining")

            if avg_att < 70:
                advice_parts.append(
                    f"Only {avg_att}% of students regularly attend {subj} classes. "
                    f"{teacher} should work with class teachers and parents to understand why students "
                    "are missing this subject. A more engaging teaching style or better scheduling "
                    "may help improve attendance."
                )
                key_issues.append(f"Low attendance: {avg_att}%")

            if at_risk > 0:
                advice_parts.append(
                    f"{at_risk} student{'s' if at_risk > 1 else ''} in {subj} "
                    f"{'are' if at_risk > 1 else 'is'} predicted to fail. "
                    f"{teacher} should identify these students, speak to them individually, "
                    "and give them extra practice and encouragement."
                )
                key_issues.append(f"{at_risk} student(s) at risk of failing")

            if improving > declining and avg_pct >= 60:
                advice_parts.append(
                    f"Students in {subj} are generally doing well and improving. "
                    f"{teacher} is doing a good job — keep up the regular practice and feedback approach."
                )
                key_issues.append("Positive trend — keep momentum")

        principal_advice = " ".join(advice_parts) if advice_parts else (
            f"{teacher} is teaching {subj} effectively. Students are on track. "
            "Continue regular assessments and feedback."
        )

        advice_list.append({
            "subject":            subj,
            "teacher":            teacher,
            "avg_predicted_pct":  avg_pct,
            "student_count":      n,
            "declining_count":    declining,
            "improving_count":    improving,
            "at_risk_count":      at_risk,
            "avg_attendance":     avg_att,
            "urgency":            urgency,
            "key_issues":         key_issues,
            "principal_advice":   principal_advice,
        })

    # Sort: high urgency first, then by avg_pct ascending
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    advice_list.sort(key=lambda x: (urgency_order[x["urgency"]], x["avg_predicted_pct"]))
    return advice_list


# =====================================================
# TEACHER — OWN SUBJECT RECOMMENDATIONS
# =====================================================

def build_teacher_own_recommendations(staff_profile, all_data: list) -> list:
    """
    For the Teacher dashboard: builds personalised, plain-language
    recommendations for the logged-in teacher about their own assigned subjects.
    Only subjects that teacher is assigned to are included.
    No algorithm or tool names anywhere.

    Returns a list of dicts, one per assigned subject. Each dict:
      subject, class_obj, section, avg_predicted_pct, student_count,
      declining_count, improving_count, at_risk_count, avg_attendance,
      urgency (high/medium/low), advice (str), action_steps (list of str)
    """
    if not staff_profile or not all_data:
        return []

    try:
        from academics.models import TeacherSubjectAssignment
    except ImportError:
        return []

    # Get this teacher's assignments
    try:
        assignments = list(
            TeacherSubjectAssignment.objects.filter(
                teacher=staff_profile
            ).select_related(
                "class_subject__subject", "class_subject__class_obj", "section"
            )
        )
    except Exception:
        return []

    if not assignments:
        return []

    # Build a key set: (subject_name, class_name, section_name)
    assigned_keys = set()
    assignment_details = {}
    for a in assignments:
        subj = a.class_subject.subject.name
        cls  = a.class_subject.class_obj.name
        sec  = a.section.name
        key  = (subj, cls, sec)
        assigned_keys.add(key)
        assignment_details[key] = {
            "subject":   subj,
            "class_obj": cls,
            "section":   sec,
        }

    # Aggregate per (subject, class, section)
    data_map = {}
    for item in all_data:
        student   = item.get("student")
        analytics = item.get("analytics", {})
        if student is None:
            continue
        try:
            cls_name = student.section.class_obj.name
            sec_name = student.section.name
        except Exception:
            continue
        att_pct = float(analytics.get("attendance_percentage", 0))
        risk    = analytics.get("risk_level", "low")
        try:
            preds = predict_future_marks(student)
        except Exception:
            preds = []
        for pred in preds:
            subj  = pred.get("subject", "")
            pct   = float(pred.get("predicted_percentage", 0))
            trend = pred.get("trend", "stable")
            key   = (subj, cls_name, sec_name)
            if key not in assigned_keys:
                continue
            if key not in data_map:
                data_map[key] = {
                    "pcts": [], "declining": 0, "improving": 0, "stable": 0,
                    "at_risk": 0, "att_pcts": [], "student_count": 0,
                    "high_risk": 0, "medium_risk": 0,
                }
            data_map[key]["pcts"].append(pct)
            data_map[key]["student_count"] += 1
            data_map[key]["att_pcts"].append(att_pct)
            data_map[key][trend] = data_map[key].get(trend, 0) + 1
            if pct < 40:
                data_map[key]["at_risk"] += 1
            if risk == "high":
                data_map[key]["high_risk"] += 1
            elif risk == "medium":
                data_map[key]["medium_risk"] += 1

    result = []
    for key, info in assignment_details.items():
        subj = info["subject"]
        cls  = info["class_obj"]
        sec  = info["section"]
        data = data_map.get(key, {})

        if not data or not data.get("pcts"):
            # No student data for this assignment yet
            result.append({
                "subject":           subj,
                "class_obj":         cls,
                "section":           sec,
                "avg_predicted_pct": 0,
                "student_count":     0,
                "declining_count":   0,
                "improving_count":   0,
                "at_risk_count":     0,
                "avg_attendance":    0,
                "urgency":           "low",
                "advice":            (
                    f"No marks have been entered yet for {subj} in Class {cls}, Section {sec}. "
                    "Please enter marks so students can be tracked and guided properly."
                ),
                "action_steps":      ["Enter marks for your students as soon as possible."],
            })
            continue

        pcts      = data["pcts"]
        avg_pct   = round(sum(pcts) / len(pcts), 2)
        avg_att   = round(sum(data["att_pcts"]) / len(data["att_pcts"]), 1) if data["att_pcts"] else 0
        n         = data["student_count"]
        declining = data.get("declining", 0)
        improving = data.get("improving", 0)
        at_risk   = data.get("at_risk", 0)
        high_risk = data.get("high_risk", 0)

        # Urgency
        if avg_pct < 40 or at_risk >= max(1, n * 0.4) or high_risk > 0:
            urgency = "high"
        elif avg_pct < 60 or declining > improving:
            urgency = "medium"
        else:
            urgency = "low"

        # Build personalised advice
        advice_parts = []
        action_steps = []

        if avg_pct < 40:
            advice_parts.append(
                f"Your {subj} class (Class {cls}, Section {sec}) has an average predicted score of "
                f"only {avg_pct}%. This means most students are likely to fail this subject. "
                "This needs your immediate attention."
            )
            action_steps.append(
                f"Identify which chapters or topics students find hardest in {subj} and reteach those."
            )
            action_steps.append(
                "Hold an extra practice session before the next exam."
            )
            action_steps.append(
                "Check each student's last test paper individually to find exactly where marks were lost."
            )
        elif avg_pct < 60:
            advice_parts.append(
                f"Your {subj} class is averaging {avg_pct}%, which is passing but not strong. "
                "Many students are in the middle range and could be pushed higher with a bit more practice."
            )
            action_steps.append(
                "Give short daily or weekly exercises to keep students practising regularly."
            )
            action_steps.append(
                "Focus on topics where students commonly make mistakes."
            )

        if declining > n * 0.3:
            advice_parts.append(
                f"{declining} out of {n} students in your {subj} class are scoring lower each term. "
                "This usually means certain topics became harder or the pace moved too fast."
            )
            action_steps.append(
                "Review the last few lessons — find the point where students started dropping and go back to it."
            )
            action_steps.append(
                "Ask students directly which topics they find confusing — they often know."
            )

        if at_risk > 0:
            advice_parts.append(
                f"{at_risk} student{'s' if at_risk > 1 else ''} in your {subj} class "
                f"{'are' if at_risk > 1 else 'is'} predicted to score below the pass mark. "
                "These students need one-on-one attention."
            )
            action_steps.append(
                f"Meet individually with the {at_risk} at-risk student{'s' if at_risk > 1 else ''} "
                "and create a short personal improvement plan for each."
            )

        if avg_att < 70:
            advice_parts.append(
                f"Student attendance in your {subj} class is only {avg_att}%. "
                "Students who miss class fall behind quickly."
            )
            action_steps.append(
                "Find out why students are missing your classes — timing, difficulty, or engagement issues."
            )
            action_steps.append(
                "Try to make lessons more interactive so students look forward to attending."
            )

        if improving > declining and avg_pct >= 60:
            advice_parts.append(
                f"Your {subj} class is doing well — {improving} students are showing improvement. "
                "Keep up the same teaching approach."
            )
            action_steps.append(
                "Continue the current approach and introduce slightly harder challenges "
                "to push improving students even further."
            )

        if not advice_parts:
            advice_parts.append(
                f"Your {subj} class (Class {cls}, Section {sec}) is performing well with an average "
                f"of {avg_pct}%. Keep maintaining this level."
            )
            action_steps.append(
                "Keep up regular assessments and feedback to maintain this performance."
            )

        result.append({
            "subject":           subj,
            "class_obj":         cls,
            "section":           sec,
            "avg_predicted_pct": avg_pct,
            "student_count":     n,
            "declining_count":   declining,
            "improving_count":   improving,
            "at_risk_count":     at_risk,
            "avg_attendance":    avg_att,
            "urgency":           urgency,
            "advice":            " ".join(advice_parts),
            "action_steps":      action_steps,
        })

    # Sort: high urgency first, then by avg_pct ascending
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda x: (urgency_order[x["urgency"]], x["avg_predicted_pct"]))
    return result
