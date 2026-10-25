# CIVICLENS AI: Security & Privacy Engineering Design

## 1. Threat Assumptions & Security Principles

CIVICLENS AI implements Defense-in-Depth across four concentric layers:
1. **Layer 1: Perimeter & Transport Defense**:
   - HTTP Strict-Transport-Security (HSTS), X-Content-Type-Options: `nosniff`, X-Frame-Options: `DENY`.
   - In-memory failed login rate-limiting (maximum 5 failed attempts per IP/username, followed by 5-minute lockout).
2. **Layer 2: Authentication, Authorization & Access Control**:
   - Salted PBKDF2-SHA256 password hashing via Werkzeug security.
   - Server-side Flask session management with `HttpOnly` and `SameSite=Lax` cookie flags.
   - Role-Based Access Control (RBAC): `admin`, `officer`, `citizen`, `public`.
   - Insecure Direct Object Reference (IDOR) prevention: Citizens are strictly restricted to inspecting complaints where `citizen_id == current_user.id`.
3. **Layer 3: Application Code & Input / Upload Safeguards**:
   - CSRF protection enabled via Flask-WTF on state-changing requests (`POST`, `PUT`, `DELETE`).
   - Jinja2 contextual HTML auto-escaping preventing Cross-Site Scripting (XSS).
   - Upload quarantine: File extension whitelist (`.jpg`, `.jpeg`, `.png`, `.pdf`), maximum 5MB size limit, UUID-prefixed file renaming, and storage outside web root.
4. **Layer 4: Data Persistence & Audit Traceability**:
   - SQLAlchemy ORM parameter binding preventing SQL Injection (zero raw SQL concatenation).
   - Immutable audit logs recording actor, action, timestamp, entity ID, and client IP.
   - Redaction of passwords, session tokens, and citizen contact info from public portals and logs.

## 2. Privacy Engineering
- Citizen phone numbers, identification documents, and private home addresses are not collected.
- Public transparency dashboards display only aggregated counts and generalized locality distributions. Precise geographic coordinates are not exposed publicly.
