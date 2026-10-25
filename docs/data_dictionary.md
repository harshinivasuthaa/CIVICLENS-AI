# CIVICLENS AI: Database Schema & Data Dictionary

All tables are implemented using SQLAlchemy ORM with foreign key constraints, indexes, and UTC timestamp standards.

## 1. Entity Models

### Table: `users`
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, Auto | Primary identifier |
| `username` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | Login identifier |
| `email` | VARCHAR(120) | UNIQUE, NOT NULL, INDEX | Contact email address |
| `password_hash` | VARCHAR(256) | NOT NULL | Salted PBKDF2-SHA256 password hash |
| `role` | VARCHAR(32) | NOT NULL, DEFAULT 'citizen' | Role: `admin`, `officer`, `citizen`, `public` |
| `department_id` | INTEGER | FK -> `departments.id`, NULLABLE | Department scope for municipal officers |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT 1 | Account enablement flag |
| `created_at` | DATETIME | NOT NULL, UTC | Account creation timestamp |

### Table: `departments`
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, Auto | Department ID |
| `dept_name` | VARCHAR(128) | UNIQUE, NOT NULL | Full department designation |
| `code` | VARCHAR(32) | UNIQUE, NOT NULL | Short departmental code (e.g. `ROADS`) |
| `sla_hours` | INTEGER | NOT NULL, DEFAULT 48 | Default resolution deadline in hours |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT 1 | Department active status |

### Table: `categories`
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, Auto | Category ID |
| `name` | VARCHAR(128) | UNIQUE, NOT NULL | Municipal grievance category name |
| `dept_id` | INTEGER | FK -> `departments.id`, NOT NULL | Mapped responsible department |
| `default_sla` | INTEGER | NOT NULL, DEFAULT 48 | Category-specific target SLA hours |
| `base_severity` | FLOAT | NOT NULL, DEFAULT 0.5 | Baseline hazard rating [0.0 to 1.0] |
| `description` | TEXT | NULLABLE | Detailed scope and examples |

### Table: `complaints`
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, Auto | Internal primary key |
| `reference_no` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | Public tracking code (`CIV-YYYYMMDD-XXXX`) |
| `citizen_id` | INTEGER | FK -> `users.id`, NULLABLE | Submitting citizen ID |
| `title` | VARCHAR(255) | NOT NULL | Grievance headline |
| `description` | TEXT | NOT NULL | Full problem narrative |
| `category_id` | INTEGER | FK -> `categories.id`, NOT NULL | Categorization ID |
| `dept_id` | INTEGER | FK -> `departments.id`, NOT NULL | Responsible department ID |
| `locality` | VARCHAR(128) | NOT NULL, INDEX | Locality, neighborhood, or ward name |
| `latitude` | FLOAT | NULLABLE | Geographic latitude coordinate |
| `longitude` | FLOAT | NULLABLE | Geographic longitude coordinate |
| `attachment_path`| VARCHAR(255) | NULLABLE | Quarantined filename with UUID prefix |
| `status` | VARCHAR(32) | NOT NULL, INDEX | Lifecycle state (8 valid states) |
| `priority_score` | FLOAT | NOT NULL, DEFAULT 0.0 | Calculated composite priority [0.0, 1.0] |
| `suggested_priority`| VARCHAR(32)| NOT NULL | Initial formula band recommendation |
| `final_priority` | VARCHAR(32) | NOT NULL | Effective band (after officer override if any) |
| `priority_override_reason` | TEXT | NULLABLE | Mandatory justification for override |
| `priority_breakdown` | TEXT | NULLABLE | JSON factor contributions |
| `delay_risk_score` | FLOAT | NOT NULL, DEFAULT 0.0 | Breach probability [0.0, 1.0] |
| `delay_risk_level` | VARCHAR(32) | NOT NULL | Low Risk / Moderate / High Delay Risk |
| `submitted_at` | DATETIME | NOT NULL, INDEX | UTC submission timestamp |
| `deadline_at` | DATETIME | NULLABLE, INDEX | Calculated operational deadline timestamp |
| `assigned_at` | DATETIME | NULLABLE | Officer dispatch timestamp |
| `resolved_at` | DATETIME | NULLABLE | Physical completion timestamp |
| `resolution_notes`| TEXT | NULLABLE | Mandatory notes when marked RESOLVED |
| `rejection_reason`| TEXT | NULLABLE | Mandatory reason when marked REJECTED |
| `is_synthetic` | BOOLEAN | NOT NULL, DEFAULT 0 | Synthetic data indicator |

### Table: `status_history`
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, Auto | History ID |
| `complaint_id` | INTEGER | FK -> `complaints.id`, NOT NULL | Target complaint ID |
| `old_status` | VARCHAR(32) | NULLABLE | Previous lifecycle status |
| `new_status` | VARCHAR(32) | NOT NULL | Transitioned lifecycle status |
| `changed_by_id` | INTEGER | FK -> `users.id`, NULLABLE | User who performed transition |
| `changed_at` | DATETIME | NOT NULL, UTC | Transition timestamp |
| `remarks` | TEXT | NULLABLE | Operational remarks and resolution notes |

### Table: `audit_logs`
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, Auto | Audit log ID |
| `actor_id` | INTEGER | FK -> `users.id`, NULLABLE | Acting user ID |
| `actor_role` | VARCHAR(32) | NULLABLE | User role at action time |
| `action` | VARCHAR(128) | NOT NULL, INDEX | Event code (`STATUS_UPDATE`, etc.) |
| `entity_type` | VARCHAR(64) | NOT NULL | Target entity type (`complaint`, `user`) |
| `entity_id` | VARCHAR(64) | NOT NULL | Target reference ID |
| `timestamp` | DATETIME | NOT NULL, UTC | Event timestamp |
| `details_json` | TEXT | NULLABLE | Sanitized metadata (secrets redacted) |
| `ip_address` | VARCHAR(45) | NULLABLE | Client remote IP address |
