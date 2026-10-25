# CIVICLENS AI: AI & Machine Learning Methodology

## 1. NLP Text Classification Subsystem

The complaint categorization engine uses a lightweight, explainable, and locally runnable natural language processing pipeline.

### Preprocessing
Raw complaint text is normalized by:
1. Converting all characters to lowercase.
2. Stripping punctuation and non-alphanumeric symbols via regex.
3. Collapsing whitespace.

### TF-IDF Vectorization
Complaint text is projected into a sparse vector space using unigrams and bigrams:
$$\text{TF}(t, d) = 1 + \ln(\text{count}(t, d)) \quad \text{for count} > 0$$
$$\text{IDF}(t) = \ln\left(\frac{1 + N}{1 + \text{DF}(t)}\right) + 1$$
Vector representations are $L_2$-normalized: $\|v\|_2 = 1.0$.

### Multinomial Logistic Regression
The classification model computes class probabilities via the softmax function:
$$P(Y = k \mid x) = \frac{\exp(w_k^T x + b_k)}{\sum_{j=1}^K \exp(w_j^T x + b_j)}$$
- **Review Threshold Gate ($\tau = 0.55$)**:
  - If $\max_k P(Y=k \mid x) \ge 0.55$: Auto-suggests predicted category and maps responsible department.
  - If $\max_k P(Y=k \mid x) < 0.55$: Flags grievance for officer manual triage.

---

## 2. Duplicate & Similar Grievance Detection

To prevent redundant dispatches while preserving citizen audit rights, the system identifies potential duplicates without deleting records:

1. **Spatiotemporal Candidate Filtering**: Queries historical complaints in the same locality submitted within the last 14 days.
2. **Cosine Similarity**:
   $$\text{sim}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2} \in [0.0, 1.0]$$
3. **Tri-Tier Matching**:
   - $\text{sim} \ge 0.85$: High Similarity (Probable Duplicate Alert)
   - $0.65 \le \text{sim} < 0.85$: Moderate Similarity (Related Chronic Issue)
   - $\text{sim} < 0.65$: Distinct Independent Issue

---

## 3. Service-Delay Risk Prediction

### Target Definition
For historical resolved complaints:
$$y = \begin{cases} 1 & \text{if } t_{\text{resolved}} > t_{\text{deadline}} \\ 0 & \text{otherwise} \end{cases}$$
Unresolved records are not falsely labeled as non-delayed (avoiding right-censoring target leakage).

### Feature Vector
No personal identifiers (citizen names, phone numbers, email) enter the feature space:
- $x_1$: Category ID
- $x_2$: Department ID
- $x_3$: Day of week ($0 = \text{Monday}, \dots, 6 = \text{Sunday}$)
- $x_4$: Submission hour ($0, \dots, 23$)
- $x_5$: Department standard SLA (hours)
- $x_6$: Active department backlog volume at submission
- $x_7$: Elapsed time ratio $\min(2.0, \frac{t_{\text{elapsed}}}{\text{SLA}})$

### Dual-Track Architecture
- **Track A (Supervised Machine Learning)**: Random Forest Classifier trained on held-out splits when $\ge 20$ historical resolved records across both classes exist.
- **Track B (Deterministic Baseline Fallback)**: Transparent backlog-velocity heuristic active during early or sparse deployment phases:
  $$P_{\text{baseline}} = 0.60 \cdot \min\left(1.0, \frac{t_{\text{elapsed}}}{\text{SLA}}\right) + 0.40 \cdot \min\left(1.0, \frac{\text{backlog}}{20}\right)$$

---

## 4. Transparent Multi-Factor Prioritization Engine

Priority score $P \in [0.0, 1.0]$ is computed using a weighted linear combination of normalized factors:
$$P = \sum_{i=1}^5 w_i \cdot x_i \quad \text{subject to} \quad \sum_{i=1}^5 w_i = 1.0$$

| Factor | Variable | Default Weight ($w_i$) | Normalization Formula |
|---|---|---|---|
| Severity | $x_{\text{sev}}$ | 0.30 | Category base severity [0.0, 1.0] + 0.20 hazard keyword boost |
| Elapsed Time | $x_{\text{time}}$ | 0.25 | $\min(1.0, \frac{t_{\text{elapsed}}}{\text{SLA}})$ |
| SLA Breach | $x_{\text{breach}}$ | 0.20 | $1.0$ if $t_{\text{elapsed}} > \text{SLA}$, else $0.0$ |
| Recurrence | $x_{\text{rec}}$ | 0.15 | $\min(1.0, \frac{\text{locality cluster count}}{5.0})$ |
| Delay Risk | $x_{\text{delay}}$ | 0.10 | Delay probability $P(\text{delay}) \in [0.0, 1.0]$ |

### Priority Bands
- $P \ge 0.70$: **Urgent Review**
- $0.40 \le P < 0.70$: **Elevated Attention**
- $P < 0.40$: **Routine Review**
All recommendations provide a complete factor breakdown. Authorized officers may override priority with a mandatory documented justification stored in the audit trail.
