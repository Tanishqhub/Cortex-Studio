import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENV = os.environ.get("ENV", "development")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENV == "production"

    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", "uploads"),
    )
    MAX_A2L_SIZE_BYTES = int(os.environ.get("MAX_A2L_SIZE_BYTES", 5 * 1024 * 1024))

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Copy backend/.env.example to backend/.env and set a real value."
        )
