"""Direct messages between friends — the inbox, a conversation thread, and
message deletion.

SECURITY MODEL (this is the highest-risk surface in the app):

- Every conversation URL is /messages/<user_id>, where <user_id> names the
  *other* participant and current_user (from the session, never from the
  URL) is always the first participant. There is no way to express "show
  me two other people's conversation" through this URL shape at all, so
  the GET/POST conversation view has no IDOR surface to guard by
  construction — every query below is built from current_user.id plus the
  named other party, never from two caller-supplied ids.
- The delete route is different: it takes a message_id, which *is* an
  independent lookup key that could name a message in a conversation the
  caller isn't part of. That route explicitly checks the loaded message's
  sender_id against current_user.id before doing anything.
- Anti-enumeration: a conversation with a real stranger (never friends, no
  history) and a conversation with a nonexistent user id both 404 the same
  way, so a response never confirms whether a given user id exists.
"""

from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_

from app.blueprints.messages import messages_bp
from app.blueprints.messages.forms import MessageForm
from app.blueprints.messages.media import delete_message_image, upload_message_image
from app.extensions import db, limiter
from app.models import Friendship, Message, NotificationType, User
from app.notifications import NotificationService
from app.time_utils import day_label
from app.uploads import InvalidUploadError


@messages_bp.app_context_processor
def inject_unread_message_count():
    """Powers the Messages nav badge in base.html — registered app-wide
    (not just for this blueprint's own routes) via app_context_processor.
    """
    if not current_user.is_authenticated:
        return {}
    count = Message.query.filter_by(recipient_id=current_user.id, read_at=None).count()
    return {"unread_message_count": count}


def _has_message_history(user_a_id, user_b_id) -> bool:
    return (
        Message.query.filter(
            or_(
                and_(Message.sender_id == user_a_id, Message.recipient_id == user_b_id),
                and_(Message.sender_id == user_b_id, Message.recipient_id == user_a_id),
            )
        ).first()
        is not None
    )


def _thread_between(user_a_id, user_b_id):
    return (
        Message.query.filter(
            or_(
                and_(Message.sender_id == user_a_id, Message.recipient_id == user_b_id),
                and_(Message.sender_id == user_b_id, Message.recipient_id == user_a_id),
            )
        )
        .order_by(Message.created_at.asc())
        .all()
    )


def _group_by_day(thread):
    """[Message, ...] -> [{"label": "Today", "messages": [...]}, ...] so the
    template can print one date separator per calendar day instead of a
    single hardcoded label over the whole thread.
    """
    groups = []
    for message in thread:
        label = day_label(message.created_at)
        if not groups or groups[-1]["label"] != label:
            groups.append({"label": label, "messages": []})
        groups[-1]["messages"].append(message)
    return groups


@messages_bp.route("")
@login_required
def inbox():
    sent_to = db.session.query(Message.recipient_id).filter(Message.sender_id == current_user.id)
    received_from = db.session.query(Message.sender_id).filter(
        Message.recipient_id == current_user.id
    )
    partner_ids = {row[0] for row in sent_to.union(received_from).all()}

    conversations = []
    for partner_id in partner_ids:
        last_message = (
            Message.query.filter(
                or_(
                    and_(Message.sender_id == current_user.id, Message.recipient_id == partner_id),
                    and_(Message.sender_id == partner_id, Message.recipient_id == current_user.id),
                )
            )
            .order_by(Message.created_at.desc())
            .first()
        )
        unread_count = Message.query.filter_by(
            sender_id=partner_id, recipient_id=current_user.id, read_at=None
        ).count()
        conversations.append(
            {
                "partner": db.session.get(User, partner_id),
                "last_message": last_message,
                "unread_count": unread_count,
            }
        )

    conversations.sort(key=lambda c: c["last_message"].created_at, reverse=True)

    return render_template("messages/inbox.html", conversations=conversations)


@messages_bp.route("/new")
@login_required
def new_message():
    # Messaging is friends-only (see conversation() below), so the only
    # valid recipients to start a fresh thread with are current_user's
    # existing friends.
    friend_ids = Friendship.friend_ids_for(current_user.id)
    friends = (
        User.query.filter(User.id.in_(friend_ids)).order_by(User.username).all()
        if friend_ids
        else []
    )
    return render_template("messages/new_message.html", friends=friends)


@messages_bp.route("/<uuid:user_id>", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per hour", methods=["POST"])
def conversation(user_id):
    other = User.query.filter_by(id=user_id).first()
    if other is None or other.id == current_user.id:
        abort(404)

    are_friends = Friendship.are_friends(current_user.id, other.id)

    # A real stranger (never friends, no message history) gets the same
    # 404 as a nonexistent user id — don't let the response confirm they
    # exist but aren't a friend.
    if not are_friends and not _has_message_history(current_user.id, other.id):
        abort(404)

    form = MessageForm()
    if form.validate_on_submit():
        # Checked again here even though the template hides the send form
        # when not are_friends — unfriending after the page loaded, or a
        # direct POST bypassing the UI, must still be rejected server-side.
        if not are_friends:
            flash("You can only message confirmed friends.", "danger")
            return redirect(url_for("messages.conversation", user_id=other.id))

        image_url = None
        image_public_id = None
        upload = form.image.data
        if upload and upload.filename:
            try:
                image_url, image_public_id = upload_message_image(upload)
            except InvalidUploadError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("messages.conversation", user_id=other.id))

        message = Message(
            sender_id=current_user.id,
            recipient_id=other.id,
            body=form.body.data,
            image_url=image_url,
            image_public_id=image_public_id,
        )
        db.session.add(message)
        NotificationService.notify(
            recipient_id=other.id,
            actor_id=current_user.id,
            type=NotificationType.MESSAGE,
            target_type="user",
            target_id=current_user.id,
        )
        db.session.commit()
        return redirect(url_for("messages.conversation", user_id=other.id))

    # Opening the thread marks incoming (unread, addressed-to-me) messages read.
    Message.query.filter_by(sender_id=other.id, recipient_id=current_user.id, read_at=None).update(
        {"read_at": datetime.now(timezone.utc)}
    )
    db.session.commit()

    thread = _thread_between(current_user.id, other.id)

    return render_template(
        "messages/conversation.html",
        other=other,
        messages=thread,
        message_groups=_group_by_day(thread),
        form=form,
        can_send=are_friends,
    )


@messages_bp.route("/<uuid:user_id>/<uuid:message_id>/delete", methods=["POST"])
@login_required
def delete_message(user_id, message_id):
    message = Message.query.get_or_404(message_id)
    # message_id is an independent lookup key — unlike the conversation
    # view, this route DOES need an explicit membership/ownership check.
    if current_user.id != message.sender_id:
        abort(403)

    if message.image_public_id:
        delete_message_image(message.image_public_id)

    db.session.delete(message)
    db.session.commit()
    flash("Message deleted.", "info")
    return redirect(url_for("messages.conversation", user_id=user_id))