# CIVICLENS AI: Deployment & Operations Guide

## 1. Local Run Instructions (Standard CSE Project Mode)

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Pip package manager

### Setup Steps
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database schema & demo accounts
python scripts/initialize_db.py

# 3. Seed demonstration complaints
python scripts/generate_sample_data.py

# 4. Train NLP classifier and Delay Risk model
python scripts/train_classifier.py
python scripts/train_delay_model.py

# 5. Launch the application
python app.py
```
Open your browser at `http://127.0.0.1:5000`.

---

## 2. Docker Container Deployment

### Build Image
```bash
docker build -t civiclens-ai:latest .
```

### Run Container
```bash
docker run -d -p 5000:5000 --name civiclens civiclens-ai:latest
```
Access the application at `http://localhost:5000`.

---

## 3. Production Deployment Notes (Scaling from SQLite to PostgreSQL)

For a multi-tenant municipal production deployment:
1. **Managed Database**: Replace the SQLite URI in `.env` with a PostgreSQL connection string:
   ```env
   DATABASE_URL=postgresql://civic_user:SecurePassword@db-host:5432/civiclens_db
   ```
2. **Reverse Proxy**: Place Nginx in front of Gunicorn for SSL/TLS termination, rate limiting, and static asset buffering.
3. **Quarantine Storage**: Mount an encrypted, non-executable persistent volume for `/app/uploads/quarantine`.
4. **Environment Secrets**: Generate a 32-byte cryptographic secret key for `SECRET_KEY`.
