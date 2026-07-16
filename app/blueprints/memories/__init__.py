from flask import Blueprint

memories_bp = Blueprint("memories", __name__)

from app.blueprints.memories import routes  # noqa: E402,F401
