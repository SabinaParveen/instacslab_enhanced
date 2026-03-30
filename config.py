"""
config.py — Application configuration
"""
import os

class Config:
    # ── Flask ──────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production-abc123')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB max upload

    # ── File Uploads ───────────────────────
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')

    # ── PostgreSQL ─────────────────────────
    # On Render, set DATABASE_URL env var (postgres://...).
    # Locally, set individual DB_* vars or edit defaults below.
    DATABASE_URL = os.environ.get('DATABASE_URL', None)
    DB_HOST     = os.environ.get('DB_HOST',     'localhost')
    DB_PORT     = int(os.environ.get('DB_PORT', 5432))
    DB_NAME     = os.environ.get('DB_NAME',     'instacslab')
    DB_USER     = os.environ.get('DB_USER',     'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
