import json
from flask import session, request
from app.models import AuditLog, db


def log_audit_event(action: str, entity_type: str, entity_id: str, details: dict = None):
    """
    Appends an immutable audit log entry for operational transparency and accountability.
    Never stores sensitive passwords or auth tokens.
    """
    try:
        actor_id = session.get("user_id") if session else None
        actor_role = session.get("role") if session else None
        ip_addr = request.remote_addr if request else None

        # Sanitize details to guarantee no secrets enter logs
        sanitized_details = {}
        if details:
            for k, v in details.items():
                if "password" in k.lower() or "token" in k.lower() or "secret" in k.lower():
                    sanitized_details[k] = "[REDACTED]"
                else:
                    sanitized_details[k] = str(v)

        entry = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details_json=json.dumps(sanitized_details) if sanitized_details else None,
            ip_address=ip_addr,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        # Avoid crashing primary user transactions due to audit logger failure
        db.session.rollback()
