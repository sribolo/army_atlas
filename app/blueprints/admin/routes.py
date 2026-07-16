"""Admin review queue and moderation actions.

Every route here is behind @admin_required — non-admins get 403, verified
in phase 1 and re-verified for each new route added in this phase. "Delete
reported content" only applies to memory/comment targets; a reported user
is handled via ban/unban instead of deletion (accounts aren't deleted
anywhere in this app).
"""

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user

from app.authorization import admin_required
from app.blueprints.admin import admin_bp
from app.blueprints.memories.media import delete_memory_media
from app.extensions import db
from app.models import Comment, Memory, Report, ReportStatus, User


@admin_bp.route("/")
@admin_required
def index():
    return redirect(url_for("admin.reports"))


def _resolve_target(report):
    """A short, human-readable description of what's being reported, plus
    the user it should be attributed to for a ban action. Handles a target
    that's already been deleted (e.g. the owner removed it themselves
    after being reported) without erroring — same graceful-fallback
    pattern as app.notifications.render_notification.
    """
    if report.target_type == "memory":
        memory = db.session.get(Memory, report.target_id)
        if memory is None:
            return "a memory that no longer exists", None
        return f"memory “{memory.title}” by {memory.user.username}", memory.user

    if report.target_type == "comment":
        comment = db.session.get(Comment, report.target_id)
        if comment is None:
            return "a comment that no longer exists", None
        return f"comment by {comment.user.username}: “{comment.body[:80]}”", comment.user

    if report.target_type == "user":
        user = db.session.get(User, report.target_id)
        if user is None:
            return "a user that no longer exists", None
        return f"user {user.username}", user

    return f"{report.target_type}:{report.target_id}", None


@admin_bp.route("/reports")
@admin_required
def reports():
    open_reports = (
        Report.query.filter_by(status=ReportStatus.OPEN)
        .order_by(Report.created_at.asc())
        .all()
    )
    rows = [(report, *_resolve_target(report)) for report in open_reports]
    return render_template("admin/reports.html", rows=rows)


@admin_bp.route("/reports/<uuid:report_id>/resolve", methods=["POST"])
@admin_required
def resolve_report(report_id):
    report = Report.query.get_or_404(report_id)
    report.status = ReportStatus.RESOLVED
    db.session.commit()
    flash("Report marked resolved.", "info")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/reports/<uuid:report_id>/delete-content", methods=["POST"])
@admin_required
def delete_reported_content(report_id):
    report = Report.query.get_or_404(report_id)

    if report.target_type == "memory":
        memory = db.session.get(Memory, report.target_id)
        if memory is not None:
            for media in memory.media:
                delete_memory_media(media.public_id, media.media_type.value)
            db.session.delete(memory)
    elif report.target_type == "comment":
        comment = db.session.get(Comment, report.target_id)
        if comment is not None:
            db.session.delete(comment)
    else:
        # Users are banned, not deleted — see ban_user/unban_user below.
        abort(400)

    report.status = ReportStatus.RESOLVED
    db.session.commit()
    flash("Content removed and report resolved.", "success")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/users/<uuid:user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't ban yourself.", "danger")
        return redirect(url_for("profiles.public_profile", username=user.username))

    user.is_active = False
    db.session.commit()
    flash(f"{user.username} has been banned.", "info")
    return redirect(url_for("profiles.public_profile", username=user.username))


@admin_bp.route("/users/<uuid:user_id>/unban", methods=["POST"])
@admin_required
def unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    flash(f"{user.username} has been unbanned.", "info")
    return redirect(url_for("profiles.public_profile", username=user.username))