# CIVICLENS AI: System Architecture Specification

## 1. Architectural Overview

CIVICLENS AI is structured as a modular 5-tier web and analytics decision-support framework designed to bridge citizen grievance submission with intelligent municipal operational dispatch:

```
+-------------------------------------------------------------------------+
|                  1. PRESENTATION & CLIENT TIER                          |
|  Bootstrap 5, Jinja2 Templates, Leaflet.js Maps, Chart.js Dashboards    |
+------------------------------------+------------------------------------+
                                     | HTTPS / JSON
+------------------------------------v------------------------------------+
|             2. APPLICATION CONTROLLER & GATEWAY TIER                    |
|  Flask Application Factory, Session Auth, Rate Limiter, CSRF Defense    |
+------------------------------------+------------------------------------+
                                     | Validated Payloads
+------------------------------------v------------------------------------+
|               3. CORE SERVICE & WORKFLOW ENGINE                         |
|  8-State Complaint Lifecycle Machine, CSV Parser, Quarantine Logger     |
+------------------------------------+------------------------------------+
                                     | Features & Embeddings
+------------------------------------v------------------------------------+
|             4. AI & ANALYTICAL INTELLIGENCE SUBSYSTEM                   |
|  TF-IDF + LogReg Classifier, Cosine Duplicate Engine, Delay RF Model,  |
|  Transparent Multi-Factor Prioritization Formula (P = SUM wi * xi)     |
+------------------------------------+------------------------------------+
                                     | Queries & Persistence
+------------------------------------v------------------------------------+
|             5. DATA PERSISTENCE & STORAGE TIER                          |
|  SQLAlchemy ORM, SQLite DB, Serialized Joblib Artifacts, Audit Logs    |
+-------------------------------------------------------------------------+
```

## 2. Complaint Lifecycle State Machine

The complaint grievance workflow transitions through 8 discrete operational states:
1. `SUBMITTED`: Registered by a citizen or ingested via bulk CSV import; unique reference code generated.
2. `UNDER_REVIEW`: Intake screening and AI classification confidence evaluation.
3. `ASSIGNED`: Formally dispatched to a departmental officer; SLA countdown begins.
4. `IN_PROGRESS`: Field teams inspecting defect and updating milestone remarks.
5. `RESOLVED`: Physical repair executed. **Strictly requires non-empty resolution notes.**
6. `CLOSED`: Resolution accepted or verified after audit window.
7. `REJECTED`: Out of municipal jurisdiction or invalid report. **Strictly requires documented rejection justification.**
8. `REOPENED`: Citizen disputes resolution within 7 days; complaint returns to active queue for re-evaluation.

## 3. Core Component Interactions
- **Live Classification Probe**: As a citizen types into the complaint form, the client issues a debounced asynchronous POST request to `/api/ai/predict-category`. The pre-trained TF-IDF Logistic Regression pipeline evaluates the text, outputting the predicted category, calibrated confidence, and recommended department.
- **Spatiotemporal Duplicate Guard**: Upon grievance creation, the candidate pool is filtered by locality and submission window (14 days). TF-IDF vectors are compared via Cosine Similarity. Matches $\ge 0.85$ generate non-destructive duplicate alerts for officer confirmation.
- **Explainable Multi-Factor Prioritization**: Prioritization is calculated via $P = \sum_{i=1}^5 w_i \cdot x_i$. All factor contributions are saved in `priority_breakdown` JSON for full transparency.
