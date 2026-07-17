"""Timed, signed tokens for password reset links.

Uses itsdangerous rather than a stored token in the database — the token is
self-verifying and expires without needing a cleanup job. To make tokens
single-use without a server-side revocation store, each token embeds a
fingerprint of the password hash it was issued against; resetting the
password changes that hash, so any older token (including a reused one)
stops verifying.
"""

import hashlib
import uuid

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.models import User

_RESET_SALT = "password-reset"
_RESET_MAX_AGE_SECONDS = 3600


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _password_fingerprint(password_hash):
    # A digest rather than the raw hash, so the reset link (which travels
    # over email and ends up in browser history) never exposes it.
    return hashlib.sha256(password_hash.encode()).hexdigest()


def generate_reset_token(user):
    payload = {"uid": str(user.id), "fp": _password_fingerprint(user.password_hash)}
    return _serializer().dumps(payload, salt=_RESET_SALT)


def verify_reset_token(token):
    """Return the User the token was issued for, or None if invalid/expired/used."""
    try:
        payload = _serializer().loads(token, salt=_RESET_SALT, max_age=_RESET_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    try:
        user = User.query.get(uuid.UUID(payload["uid"]))
    except (ValueError, TypeError, KeyError):
        return None

    if user is None or payload.get("fp") != _password_fingerprint(user.password_hash):
        return None

    return user
