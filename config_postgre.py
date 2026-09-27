import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    _url = os.environ.get('DATABASE_URL', 'postgresql+psycopg2://charo:charongua89@localhost/bookshop')

    # pythonanywhere / heroku give "postgres://" — SQLAlchemy 2.x rejects it
    if _url.startswith("postgres://"):
        _url = _url.replace("postgres://", "postgresql+psycopg2://", 1)
    # If it's "postgresql://" with no driver, force psycopg2
    elif _url.startswith("postgresql://"):
        _url = _url.replace("postgresql://", "postgresql+psycopg2://", 1)

    SQLALCHEMY_DATABASE_URI = _url
    SQLALCHEMY_TRACK_MODIFICATIONS = False