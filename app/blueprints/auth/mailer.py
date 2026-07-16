"""Password reset email delivery.

When MAIL_SUPPRESS_SEND is on (always true in development/testing, see
app/config.py) the link is logged instead, so the reset flow works without a
configured mail server.
"""

from flask import current_app
from flask_mail import Message

from app.extensions import mail


def send_password_reset_email(user, reset_url):
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info("Password reset link for %s: %s", user.email, reset_url)
        return

    message = Message(
        subject="Reset your ARMY Atlas password",
        recipients=[user.email],
        body=(
            f"Someone requested a password reset for your ARMY Atlas account.\n\n"
            f"Reset your password: {reset_url}\n\n"
            f"This link expires in 1 hour. If you didn't request this, ignore this email."
        ),
    )
    mail.send(message)
