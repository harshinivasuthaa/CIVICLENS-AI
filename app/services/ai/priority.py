import json
from datetime import datetime, timezone, timedelta
from app.models import Complaint, SystemConfig, db
from .delay_model import delay_service

CRITICAL_HAZARD_KEYWORDS = [
    "spark", "electric wire", "short circuit", "flooding", "collapsed",
    "collapse", "hazardous", "accident", "cave in", "manhole open",
    "gas leak", "chemical", "poisonous", "drowning", "ambulance",
]

DEFAULT_WEIGHTS = {
    "severity": 0.30,
    "elapsed_time": 0.25,
    "sla_breach": 0.20,
    "recurrence": 0.15,
    "delay_risk": 0.10,
}


def get_configured_weights() -> dict:
    """Retrieves dynamic weights from SystemConfig or returns defaults."""
    cfg = SystemConfig.query.filter_by(key="priority_weights").first()
    if cfg:
        try:
            weights = json.loads(cfg.value)
            total = sum(weights.values())
            if 0.99 <= total <= 1.01:
                return weights
        except Exception:
            pass
    return DEFAULT_WEIGHTS


def calculate_priority_score(complaint: Complaint) -> dict:
    """
    Computes transparent multi-factor priority score:
    P = w1*x_sev + w2*x_time + w3*x_breach + w4*x_rec + w5*x_delay
    """
    weights = get_configured_weights()
    missing_fields = []

    # 1. Severity Factor (x_sev in [0, 1])
    base_sev = 0.5
    if complaint.category and complaint.category.base_severity is not None:
        base_sev = complaint.category.base_severity
    else:
        missing_fields.append("category_base_severity")

    text_lower = f"{complaint.title} {complaint.description}".lower()
    keyword_boost = 0.2 if any(kw in text_lower for kw in CRITICAL_HAZARD_KEYWORDS) else 0.0
    x_sev = min(1.0, base_sev + keyword_boost)

    # 2. Elapsed Time Ratio (x_time in [0, 1])
    sla_hours = 48.0
    if complaint.category and complaint.category.default_sla:
        sla_hours = float(complaint.category.default_sla)
    elif complaint.department and complaint.department.sla_hours:
        sla_hours = float(complaint.department.sla_hours)
    else:
        missing_fields.append("department_sla_hours")

    now_utc = datetime.now(timezone.utc)
    sub = complaint.submitted_at.replace(tzinfo=timezone.utc) if complaint.submitted_at.tzinfo is None else complaint.submitted_at
    elapsed_hours = max(0.0, (now_utc - sub).total_seconds() / 3600.0)
    x_time = min(1.0, elapsed_hours / max(1.0, sla_hours))

    # 3. SLA Breach Urgency (x_breach in {0, 1})
    x_breach = 1.0 if elapsed_hours > sla_hours else 0.0

    # 4. Recurrence Factor (x_rec in [0, 1])
    cutoff = now_utc - timedelta(days=14)
    cluster_count = Complaint.query.filter(
        Complaint.locality.ilike(complaint.locality.strip()),
        Complaint.submitted_at >= cutoff,
        Complaint.id != complaint.id,
    ).count()
    x_rec = min(1.0, cluster_count / 5.0)

    # 5. Delay Risk Factor (x_delay in [0, 1])
    delay_res = delay_service.predict_delay_risk(complaint)
    x_delay = delay_res.get("delay_risk_score", 0.0)

    # Weighted Sum Formula
    p_score = (
        weights["severity"] * x_sev
        + weights["elapsed_time"] * x_time
        + weights["sla_breach"] * x_breach
        + weights["recurrence"] * x_rec
        + weights["delay_risk"] * x_delay
    )
    p_score = round(min(1.0, max(0.0, p_score)), 3)

    if p_score >= 0.70:
        band = "Urgent Review"
        explanation = "High composite priority: elevated safety risk, overdue status, or critical backlog concentration."
    elif p_score >= 0.40:
        band = "Elevated Attention"
        explanation = "Moderate operational attention required: nearing SLA limit or recurring locality pattern."
    else:
        band = "Routine Review"
        explanation = "Standard municipal queue scheduling within established SLA parameters."

    breakdown = {
        "severity": {"factor_value": round(x_sev, 3), "weight": weights["severity"], "contribution": round(weights["severity"] * x_sev, 3)},
        "elapsed_time": {"factor_value": round(x_time, 3), "weight": weights["elapsed_time"], "contribution": round(weights["elapsed_time"] * x_time, 3)},
        "sla_breach": {"factor_value": round(x_breach, 1), "weight": weights["sla_breach"], "contribution": round(weights["sla_breach"] * x_breach, 3)},
        "recurrence": {"factor_value": round(x_rec, 3), "weight": weights["recurrence"], "contribution": round(weights["recurrence"] * x_rec, 3), "local_active_cluster": cluster_count},
        "delay_risk": {"factor_value": round(x_delay, 3), "weight": weights["delay_risk"], "contribution": round(weights["delay_risk"] * x_delay, 3)},
    }

    return {
        "priority_score": p_score,
        "suggested_priority": band,
        "explanation": explanation,
        "breakdown": breakdown,
        "delay_risk_level": delay_res.get("delay_risk_level"),
        "delay_risk_score": x_delay,
        "delay_risk_factors": delay_res.get("contributing_factors"),
        "missing_fields": missing_fields,
        "requires_human_review": p_score >= 0.70 or bool(missing_fields),
    }


def update_complaint_priority(complaint: Complaint):
    """Calculates and updates priority and delay fields in the complaint record."""
    res = calculate_priority_score(complaint)
    complaint.priority_score = res["priority_score"]
    complaint.suggested_priority = res["suggested_priority"]
    if not complaint.priority_override_reason:
        complaint.final_priority = res["suggested_priority"]
    complaint.priority_breakdown = json.dumps(res["breakdown"])
    complaint.delay_risk_score = res["delay_risk_score"]
    complaint.delay_risk_level = res["delay_risk_level"]
    complaint.delay_risk_factors = json.dumps(res["delay_risk_factors"])
    db.session.commit()
    return res
