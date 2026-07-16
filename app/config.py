"""Configuration classes for ARMY Atlas.

SECRET_KEY and DATABASE_URL are always read from the environment. Nothing
sensitive is hardcoded here or in .env.example.
"""

import os


class Config:
    """Base configuration shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie hardening.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_ENABLED = True

    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # Password reset emails. MAIL_SUPPRESS_SEND logs the link to the console
    # instead of sending mail — always on in dev/testing, env-controlled
    # (default off) in production.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@armyatlas.local")
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"

    # Cloudinary (profile picture storage).
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

    # Hard cap on request body size — defense in depth ahead of the
    # content-based validation in app/uploads.py. Sized for the worst case
    # of a memory's multiple photos/videos (see MAX_FILES_PER_MEMORY and
    # per-file limits in app/blueprints/memories/media.py), not just a
    # single profile picture.
    MAX_CONTENT_LENGTH = 160 * 1024 * 1024

    @classmethod
    def init_app(cls, app):
        """Hook for per-environment startup checks. No-op by default."""


class DevelopmentConfig(Config):
    DEBUG = True
    # Allow plain HTTP on localhost during development.
    SESSION_COOKIE_SECURE = False
    # No mail server in dev — log reset links to the console instead.
    MAIL_SUPPRESS_SEND = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    MAIL_SUPPRESS_SEND = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )


class ProductionConfig(Config):
    DEBUG = False

    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production."
            )
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError(
                "DATABASE_URL environment variable must be set in production."
            )


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
