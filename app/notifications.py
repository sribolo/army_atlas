"""The single write path for notifications, plus the display-text renderer.

NotificationService.notify() is the *only* thing that should ever create a
Notification row. The comment/like routes (memories blueprint) and the
follow/friend-request routes (social blueprint) all call through here
instead of writing to the table directly.
"""

from flask import url_for

from app.extensions import db
from app.models import Memory, Notification, NotificationType


class NotificationService:
    """Stateless — every method is a staticmethod operating on the current
    db.session, matching the rest of this app's model/query style.
    """

    @staticmethod
    def notify(*, recipient_id, actor_id, type: NotificationType, target_type: str, target_id):
        """Create a notification, or return None if it was skipped.

        Skips:
        - notifying a user of their own action (actor == recipient) —
          liking or commenting on your own memory never notifies you.
        - creating a duplicate *unread* notification for the same actor,
          type, and target — e.g. unliking then re-liking before the first
          notification was read doesn't spam a second one.

        Adds to the session but does not commit; it's meant to ride along
        in the same transaction as the action that triggered it.
        """
        if actor_id == recipient_id:
            return None

        duplicate = Notification.query.filter_by(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type=type,
            target_type=target_type,
            target_id=target_id,
            read_at=None,
        ).first()
        if duplicate is not None:
            return None

        notification = Notification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type=type,
            target_type=target_type,
            target_id=target_id,
        )
        db.session.add(notification)
        return notification


def render_notification(notification: Notification) -> str:
    """Display text for a notification. Never raises — a deleted target
    (memory, friend request, ...) renders a graceful fallback instead of
    crashing the notifications page.
    """
    actor_name = notification.actor.username

    if notification.type == NotificationType.COMMENT:
        memory = db.session.get(Memory, notification.target_id)
        if memory is not None:
            return f"{actor_name} commented on your memory “{memory.title}”."
        return f"{actor_name} commented on a memory you posted."

    if notification.type == NotificationType.LIKE:
        memory = db.session.get(Memory, notification.target_id)
        if memory is not None:
            return f"{actor_name} liked your memory “{memory.title}”."
        return f"{actor_name} liked a memory you posted."

    if notification.type == NotificationType.FOLLOW:
        return f"{actor_name} started following you."

    if notification.type == NotificationType.FRIEND_REQUEST:
        return f"{actor_name} sent you a friend request."

    if notification.type == NotificationType.MESSAGE:
        # target is the sender themself (there's no separate conversation
        # entity to look up) — see app/blueprints/messages/routes.py.
        return f"{actor_name} sent you a message."

    return f"{actor_name} did something."  # unreachable given the enum, but never crash


def notification_url(notification: Notification) -> str:
    """Where clicking a notification should land. Mirrors render_notification's
    never-crash contract — a deleted target falls back to the notifications
    list itself rather than a broken link.
    """
    if notification.type in (NotificationType.COMMENT, NotificationType.LIKE):
        memory = db.session.get(Memory, notification.target_id)
        if memory is not None:
            return url_for("memories.memory_detail", memory_id=memory.id)
        return url_for("social.notifications")

    if notification.type == NotificationType.FOLLOW:
        return url_for("profiles.public_profile", username=notification.actor.username)

    if notification.type == NotificationType.FRIEND_REQUEST:
        # No single-request detail page — Accept/Decline both live on the
        # requests inbox, so that's the useful landing spot.
        return url_for("social.friend_requests")

    if notification.type == NotificationType.MESSAGE:
        return url_for("messages.conversation", user_id=notification.actor_id)

    return url_for("social.notifications")  # unreachable given the enum, but never crash
