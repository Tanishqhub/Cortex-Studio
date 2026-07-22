import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENV = os.environ.get("ENV", "development")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENV == "production"

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Copy backend/.env.example to backend/.env and set a real value."
        )
