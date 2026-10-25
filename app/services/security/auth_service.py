import time
from flask import session, request
from app.models import User, db

# In-memory failed login tracking for brute-force rate limiting: {ip_or_user: [timestamps]}
FAILED_ATTEMPTS = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes


def is_rate_limited(identifier: str) -> bool:
    """Checks whether an IP address or username has exceeded failed login threshold."""
    now = time.time()
    attempts = FAILED_ATTEMPTS.get(identifier, [])
    # Filter attempts within the lockout window
    recent = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
    FAILED_ATTEMPTS[identifier] = recent
    return len(recent) >= MAX_FAILED_ATTEMPTS


def record_failed_attempt(identifier: str):
    """Records a failed authentication attempt."""
    now = time.time()
    attempts = FAILED_ATTEMPTS.get(identifier, [])
    attempts.append(now)
    FAILED_ATTEMPTS[identifier] = attempts


def reset_failed_attempts(identifier: str):
    """Clears failed attempts on successful authentication."""
    FAILED_ATTEMPTS.pop(identifier, None)


def login_user(user: User):
    """Establishes an authenticated session for the given user."""
    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    session["department_id"] = user.department_id
    session.permanent = True


def logout_user():
    """Invalidates the current session completely."""
    session.clear()


def get_current_user():
    """Fetches the currently authenticated User instance from the database."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)
