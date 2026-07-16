"""Extension singletons, shared across the app factory and blueprints.

Every extension is instantiated here without an app, then bound to a
concrete Flask app inside create_app(). Nothing here touches a global app
object.
"""

import uuid

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.session_protection = "strong"
login_manager.login_view = "auth.login"
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
mail = Mail()


@login_manager.user_loader
def load_user(user_id):
    # Imported lazily to avoid a circular import between extensions and models.
    from app.models import User

    try:
        return db.session.get(User, uuid.UUID(user_id))
    except (ValueError, AttributeError):
        return None
