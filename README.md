# CIVICLENS AI
### Citizen Complaint Classification, Public Service Delay Prediction and Transparent Municipal Issue Prioritization Framework

An intelligent municipal complaint management and public-service analytics framework built with **Python Flask, SQLite/SQLAlchemy, Scikit-learn, Pandas, Chart.js, and Leaflet.js**. It bridges citizen reporting with automated NLP triage, spatiotemporal duplicate detection, statistical service-delay prediction, and an explainable multi-factor prioritization engine.

---

## 1. Project Objectives & Engineering Areas

CIVICLENS AI demonstrates four core engineering disciplines in an integrated, locally runnable system:

- **Data Engineering**: Robust CSV ingestion pipelines, Pydantic/schema validation, text normalization, non-destructive quarantine logging, spatiotemporal indexing, and data quality audits.
- **Cloud & Deployment Engineering**: Containerized deployable architecture (`Dockerfile`), environment-based configuration, WSGI Gunicorn readiness, health check endpoints (`/health`), and scaling paths from SQLite to PostgreSQL.
- **AI & ML Engineering**: NLP complaint categorization (TF-IDF + Logistic Regression) with confidence triage, Cosine Similarity duplicate detection, Random Forest service-delay prediction with an operational baseline fallback, and transparent multi-factor priority scoring.
- **Security Engineering**: Defense-in-depth security, PBKDF2-SHA256 password hashing, server-side session guards, Role-Based Access Control (RBAC), CSRF protection, upload quarantine with UUID sanitization, and IDOR isolation preventing cross-citizen data leaks.

*Note: CIVICLENS AI is a decision-support framework. It does not replace municipal authorities or automatically resolve physical complaints.*

---

## 2. Technology Stack

| Layer | Technologies |
|---|---|
| **Backend Web Framework** | Python 3.12, Flask 3.1, Flask-WTF, Jinja2 |
| **Database & ORM** | SQLite, SQLAlchemy 2.0, Flask-SQLAlchemy |
| **Machine Learning & NLP** | Scikit-learn (TF-IDF, Logistic Regression, Random Forest), NumPy, SciPy |
| **Data Processing & Import** | Pandas, CSV DictReader, Hashlib |
| **Frontend UI & Visualization** | Bootstrap 5.3, Bootstrap Icons, Chart.js 4.4, Leaflet.js 1.9 |
| **Testing & Quality** | Pytest 9.1 (20 Automated Unit/Integration Tests) |
| **Containerization** | Docker, Gunicorn WSGI |

---

## 3. Demonstration Accounts & Credentials

The framework comes pre-seeded with fictional accounts for presentation and viva demonstrations:

| Role | Username | Password | Assigned Scope | Key Capabilities |
|---|---|---|---|---|
| **Administrator** | `admin` | `Admin@123` | System-Wide | User management, CSV batch imports, data quality, config |
| **Municipal Officer** | `officer_road` | `Officer@123` | Roads & Highways | Triage queue, status transitions, priority override, duplicate review |
| **Municipal Officer** | `officer_waste` | `Officer@123` | Solid Waste | Waste queue triage, resolution notes, department alerts |
| **Citizen** | `citizen_jane` | `Citizen@123` | Personal Grievances | Submit complaints, live AI triage, track status, post remarks |
| **Citizen** | `citizen_john` | `Citizen@123` | Personal Grievances | Submit complaints, view personal timeline, dispute & reopen |
| **Public Viewer** | *No Login Needed* | *N/A* | Public Portal (`/`) | Aggregated municipal KPIs, category distribution, non-PII hotspots |

---

## 4. Local Installation & Setup

### Step 1: Clone or Navigate to Project Directory
```powershell
cd "d:\Civiclens AI"
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Initialize Database & Seed Master Entities
```powershell
python scripts/initialize_db.py
```
*Creates all database tables, 8 municipal departments, 8 categories, system configuration, and the 5 demo user accounts.*

### Step 4: Generate Demonstration Grievance Dataset
```powershell
python scripts/generate_sample_data.py
```
*Populates 500 realistic municipal complaints across all 8 categories with consistent lifecycle timelines.*

### Step 5: Train NLP Classifier & Delay Prediction Model
```powershell
python scripts/train_classifier.py
python scripts/train_delay_model.py
```
*Trains and serializes Scikit-learn model artifacts to `app/services/ai/artifacts/` with held-out test evaluation.*

### Step 6: Start Application Server
```powershell
python app.py
```
Open your web browser and navigate to:
**`http://127.0.0.1:5000`**

---

## 5. Automated Test Suite Execution

Run all 20 automated unit and integration tests using Pytest:
```powershell
python -m pytest -v
```

### Test Coverage Highlights:
- `test_auth.py`: Login, invalid credentials rejection, logout, RBAC guards, and IDOR citizen data isolation.
- `test_complaints.py`: Complaint registration, field validation, status transitions, mandatory resolution notes.
- `test_data_engineering.py`: CSV parsing, malformed row quarantine, data quality index calculation.
- `test_ai_classifier.py`: TF-IDF inference structure, low-confidence thresholding ($\tau < 0.55$), text cleanup.
- `test_delay_priority.py`: Delay risk prediction, transparent priority formula ($P = \sum w_i x_i$), override justifications.
- `test_security.py`: File extension whitelist (.jpg, .png, .pdf allowed; scripts blocked), `/health` probe, PII redaction.

---

## 6. Transparent Multi-Factor Prioritization Formula

Grievance urgency is computed transparently using normalized criteria:
$$P = w_1 x_{\text{sev}} + w_2 x_{\text{time}} + w_3 x_{\text{breach}} + w_4 x_{\text{rec}} + w_5 x_{\text{delay}}$$
Subject to:
$$\sum_{i=1}^5 w_i = 1.0 \quad \text{and} \quad x_i \in [0.0, 1.0]$$

| Factor | Factor Symbol | Default Weight | Description |
|---|---|---|---|
| **Severity** | $x_{\text{sev}}$ | **0.30** | Category base hazard + keyword safety escalations |
| **Elapsed Time** | $x_{\text{time}}$ | **0.25** | Elapsed hours / Target departmental SLA |
| **SLA Breach** | $x_{\text{breach}}$ | **0.20** | Binary urgency flag ($1.0$ if overdue, else $0.0$) |
| **Recurrence** | $x_{\text{rec}}$ | **0.15** | Cluster density of complaints in the same locality |
| **Delay Risk** | $x_{\text{delay}}$ | **0.10** | Statistical probability of exceeding deadline |

### Priority Bands:
- $P \ge 0.70$: **Urgent Review** (Red badge)
- $0.40 \le P < 0.70$: **Elevated Attention** (Yellow badge)
- $P < 0.40$: **Routine Review** (Green badge)

---

## 7. Project Structure

```
Civiclens AI/
├── app.py                      # Application entry point
├── config.py                   # Environment configuration (Dev, Prod, Test)
├── requirements.txt            # Pinned dependencies
├── .env.example                # Environment variables template
├── Dockerfile                  # Container definition
├── README.md                   # System documentation
├── instance/                   # Local SQLite database instance
├── app/
│   ├── __init__.py             # Flask factory, filters, error handlers
│   ├── models/                 # SQLAlchemy models (User, Complaint, Batch, Audit)
│   ├── routes/                 # Blueprints (auth, citizen, officer, admin, analytics, ai_api)
│   ├── services/
│   │   ├── ai/                 # NLP Classifier, Duplicate, Delay Model, Priority Engine
│   │   ├── data_engineering/  # CSV Importer, Exporter, Data Quality
│   │   ├── security/          # Auth, RBAC decorators, Upload quarantine, Audit logger
│   ├── static/                 # CSS theme, JS controllers, Map/Chart renderers
│   ├── templates/              # Jinja2 modular templates (citizen, officer, admin, analytics)
├── datasets/
│   ├── samples/                # Sample datasets
│   ├── templates/              # Downloadable CSV templates
├── scripts/
│   ├── initialize_db.py        # Seed roles, departments, categories, users
│   ├── generate_sample_data.py # 500 synthetic complaints generator
│   ├── train_classifier.py     # Train & evaluate TF-IDF classifier
│   ├── train_delay_model.py    # Train & evaluate Random Forest delay model
│   ├── evaluate_models.py      # Evaluation metrics summary
│   ├── import_dataset.py       # CLI CSV batch import utility
├── tests/                      # 20 Pytest unit & integration tests
└── docs/                       # Academic design documents (Architecture, AI, Security)
```

---

## 8. Academic Integrity & Ethics Notice

- All demo grievances containing synthetic outcomes are explicitly labeled (`is_synthetic = True`).
- No personal data or government identification numbers are collected or stored.
- Machine learning confidence values represent statistical estimates and are paired with a deterministic baseline when data is sparse.
