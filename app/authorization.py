"""Reusable authorization helpers: ownership checks, admin gating, and ban
enforcement.

These are resource-shape-agnostic so memories and messages can reuse them
in later phases without depending on the profiles blueprint.
"""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required, logout_user


def enforce_active_user():
    """Force-logout a user whose account was banned (is_active=False)
    mid-session.

    Flask-Login only checks is_active at login time by default (see
    app/blueprints/auth/routes.py's login()) — an existing session would
    otherwise keep working until it naturally expired even after a ban.
    Registered once, app-wide, as a before_request hook in create_app(),
    so every request — not just @login_required-guarded ones — re-checks
    this before anything else runs.
    """
    if current_user.is_authenticated and not current_user.is_active:
        logout_user()


def require_ownership(owner_id):
    """Abort 403 unless the current user owns the resource.

    Callers load the resource themselves and pass the id of its owner:

        user = User.query.filter_by(username=username).first_or_404()
        require_ownership(user.id)
    """
    if not current_user.is_authenticated or current_user.id != owner_id:
        abort(403)


def admin_required(view):
    """Guard a route so only authenticated admins can reach it."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
