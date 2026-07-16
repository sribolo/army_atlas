from flask import Blueprint

concerts_bp = Blueprint("concerts", __name__)

from app.blueprints.concerts import routes  # noqa: E402,F401
