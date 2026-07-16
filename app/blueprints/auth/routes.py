"""Registration, login, logout, and password reset.

Login failures and reset requests always return the same generic message
regardless of whether the username/email exists, to avoid leaking account
existence (anti-enumeration).
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import (
    LoginForm,
    PasswordResetForm,
    PasswordResetRequestForm,
    RegisterForm,
)
from app.blueprints.auth.mailer import send_password_reset_email
from app.blueprints.auth.tokens import generate_reset_token, verify_reset_token
from app.extensions import db, limiter
from app.models import User
from app.security import hash_password, verify_password

GENERIC_LOGIN_ERROR = "Invalid username or password."
GENERIC_RESET_MESSAGE = "If an account with that email exists, a reset link has been sent."


def _safe_next_url(candidate):
    """Only allow same-site relative redirects after login."""
    if candidate and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return None


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
            password_hash=hash_password(form.password.data),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to ARMY Atlas! 💜", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.is_active and verify_password(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_url = _safe_next_url(request.args.get("next"))
            return redirect(next_url or url_for("main.index"))
        flash(GENERIC_LOGIN_ERROR, "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/reset", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def reset_request():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            reset_url = url_for(
                "auth.reset_password", token=generate_reset_token(user), _external=True
            )
            send_password_reset_email(user, reset_url)
        flash(GENERIC_RESET_MESSAGE, "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_request.html", form=form)


@auth_bp.route("/reset/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def reset_password(token):
    user = verify_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.reset_request"))

    form = PasswordResetForm()
    if form.validate_on_submit():
        user.password_hash = hash_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset. You can log in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
