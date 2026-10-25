import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration with secure defaults."""
    SECRET_KEY = os.getenv("SECRET_KEY", "civiclens-ai-insecure-dev-key-change-in-production-2026")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload configurations
    UPLOAD_FOLDER = BASE_DIR / "uploads" / "quarantine"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    PERMANENT_SESSION_LIFETIME = 3600 * 8  # 8 hours

    # AI and Classification Config
    AI_CONFIDENCE_THRESHOLD = 0.55  # Below this, flag for human officer triage
    SIMILARITY_DUPLICATE_THRESHOLD = 0.85
    SIMILARITY_RELATED_THRESHOLD = 0.65

    # Priority formula weights: sum must equal 1.0
    PRIORITY_WEIGHTS = {
        "severity": 0.30,
        "elapsed_time": 0.25,
        "sla_breach": 0.20,
        "recurrence": 0.15,
        "delay_risk": 0.10,
    }


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'civiclens_dev.db'}"
    )


class TestingConfig(Config):
    """Testing configuration with in-memory or isolated test database."""
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False  # Allows streamlined programmatic test posts
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = BASE_DIR / "instance" / "test_uploads"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'civiclens_prod.db'}")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
