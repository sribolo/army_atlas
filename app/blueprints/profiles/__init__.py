from flask import Blueprint

profiles_bp = Blueprint("profiles", __name__)

from app.blueprints.profiles import routes  # noqa: E402,F401
