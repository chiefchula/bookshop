import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# Load .env from the directory containing config.py, regardless of CWD
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')

    # Prefer DATABASE_URL from .env; fall back to a local SQLite file
    _url = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + str(Path(__file__).resolve().parent / 'bookshop.db')
    )

    # Normalise common Postgres URL styles so you can switch back later if needed
    if _url.startswith("postgres://"):
        _url = _url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif _url.startswith("postgresql://"):
        _url = _url.replace("postgresql://", "postgresql+psycopg2://", 1)

    SQLALCHEMY_DATABASE_URI = _url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)   # absolute max
    SESSION_IDLE_TIMEOUT = 30 * 60                     # 30 minutes idle
    SESSION_REFRESH_EACH_REQUEST = True