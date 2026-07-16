"""Timed, signed tokens for password reset links.

Uses itsdangerous rather than a stored token in the database — the token is
self-verifying and expires without needing a cleanup job.
"""

import uuid

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.models import User

_RESET_SALT = "password-reset"
_RESET_MAX_AGE_SECONDS = 3600


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_reset_token(user):
    return _serializer().dumps(str(user.id), salt=_RESET_SALT)


def verify_reset_token(token):
    """Return the User the token was issued for, or None if invalid/expired."""
    try:
        user_id = _serializer().loads(token, salt=_RESET_SALT, max_age=_RESET_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    try:
        return User.query.get(uuid.UUID(user_id))
    except (ValueError, TypeError):
        return None
