"""Application factory for ARMY Atlas."""

import os

import cloudinary
from flask import Flask

from app.authorization import enforce_active_user
from app.cli import register_cli
from app.config import config
from app.extensions import csrf, db, limiter, login_manager, mail, migrate


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    _init_extensions(app)
    _init_cloudinary(app)
    _register_blueprints(app)
    _register_template_filters(app)
    _register_template_globals(app)
    register_cli(app)
    app.before_request(enforce_active_user)

    return app


def _register_template_filters(app):
    from app.flags import country_flag
    from app.time_utils import time_ago

    app.jinja_env.filters["flag"] = country_flag
    app.jinja_env.filters["timeago"] = time_ago


def _register_template_globals(app):
    """static_url(filename): url_for('static', ...) plus a ?v=<mtime>
    cache-buster, so editing e.g. atlas.css is guaranteed to invalidate
    every browser's cached copy on next load instead of requiring users
    (or us, mid-development) to hard-refresh.
    """
    from flask import url_for

    def static_url(filename):
        path = os.path.join(app.static_folder, filename)
        try:
            version = int(os.path.getmtime(path))
        except OSError:
            version = 0
        return url_for("static", filename=filename, v=version)

    app.jinja_env.globals["static_url"] = static_url


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)

    # Import models so their tables are registered on db.metadata before
    # `flask db migrate` inspects it.
    from app import models  # noqa: F401


def _init_cloudinary(app):
    cloudinary.config(
        cloud_name=app.config.get("CLOUDINARY_CLOUD_NAME"),
        api_key=app.config.get("CLOUDINARY_API_KEY"),
        api_secret=app.config.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )


def _register_blueprints(app):
    from app.blueprints.admin import admin_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.concerts import concerts_bp
    from app.blueprints.main import main_bp
    from app.blueprints.memories import memories_bp
    from app.blueprints.messages import messages_bp
    from app.blueprints.profiles import profiles_bp
    from app.blueprints.social import social_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    # No prefix: profile routes are /u/<username> and /u/<username>/edit.
    app.register_blueprint(profiles_bp)
    # No prefix: routes are /concerts, /concerts/<id>.
    app.register_blueprint(concerts_bp)
    # No prefix: routes are /concerts/<id>/memories/new and /memories/<id>...
    app.register_blueprint(memories_bp)
    # No prefix: routes are /u/<username>/follow, /feed, /friend-requests...
    app.register_blueprint(social_bp)
    app.register_blueprint(messages_bp, url_prefix="/messages")
    app.register_blueprint(admin_bp, url_prefix="/admin")
