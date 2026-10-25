from functools import wraps
from flask import session, redirect, url_for, flash, abort, request
from app.models import Complaint, db


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this resource.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def roles_accepted(*roles):
    """Restricts endpoint access to users possessing any of the designated roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Authentication required.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            
            user_role = session.get("role")
            if user_role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def citizen_owns_complaint(f):
    """Enforces IDOR prevention: ensures a citizen can only inspect their own complaint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        reference_no = kwargs.get("reference_no")
        user_id = session.get("user_id")
        user_role = session.get("role")

        if not user_id:
            return redirect(url_for("auth.login"))

        complaint = Complaint.query.filter_by(reference_no=reference_no).first_or_404()

        # Admins and Officers have authorized staff scope
        if user_role in ("admin", "officer"):
            return f(*args, **kwargs)

        # Citizens must match citizen_id exactly
        if complaint.citizen_id != user_id:
            abort(403)

        return f(*args, **kwargs)
    return decorated_function
