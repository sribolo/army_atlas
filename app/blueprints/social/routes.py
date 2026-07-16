"""Follow/unfollow, the friend request lifecycle, and the feed.

Follow and unfollow, and unfriend, are scoped entirely by the current
session plus a target username in the URL — there's no separate
followed/friendship id a caller could substitute to act on someone else's
relationship, so there's no IDOR surface to guard there. Accepting,
declining, and canceling a friend request DO take a request id, so those
are guarded with app.authorization.require_ownership: accept/decline
require the current user to be the receiver, cancel requires the sender.
"""

from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.authorization import require_ownership
from app.blueprints.social import social_bp
from app.extensions import db, limiter
from app.models import (
    Attendance,
    Concert,
    Follow,
    FriendRequest,
    FriendRequestStatus,
    Friendship,
    Memory,
    MemoryLike,
    MemoryVisibility,
    Notification,
    NotificationType,
    User,
)
from app.notifications import NotificationService, notification_url, render_notification
from app.social_graph import can_view_memory

FEED_PER_PAGE = 20


@social_bp.app_context_processor
def inject_nav_badge_counts():
    """Powers the nav badges in base.html — registered app-wide (not just
    for this blueprint's own routes) via app_context_processor.
    """
    if not current_user.is_authenticated:
        return {}
    return {
        "pending_friend_request_count": FriendRequest.query.filter_by(
            receiver_id=current_user.id, status=FriendRequestStatus.PENDING
        ).count(),
        "unread_notification_count": Notification.query.filter_by(
            recipient_id=current_user.id, read_at=None
        ).count(),
    }


# --- follow / unfollow -----------------------------------------------------


@social_bp.route("/u/<username>/follow", methods=["POST"])
@login_required
def follow_user(username):
    target = User.query.filter_by(username=username).first_or_404()
    if target.id == current_user.id:
        flash("You can't follow yourself.", "danger")
        return redirect(url_for("profiles.public_profile", username=username))

    already = Follow.query.filter_by(follower_id=current_user.id, followed_id=target.id).first()
    if already is None:
        db.session.add(Follow(follower_id=current_user.id, followed_id=target.id))
        NotificationService.notify(
            recipient_id=target.id,
            actor_id=current_user.id,
            type=NotificationType.FOLLOW,
            target_type="user",
            target_id=current_user.id,
        )
        db.session.commit()
        flash(f"You're now following {target.username}.", "success")
    return redirect(url_for("profiles.public_profile", username=username))


@social_bp.route("/u/<username>/unfollow", methods=["POST"])
@login_required
def unfollow_user(username):
    target = User.query.filter_by(username=username).first_or_404()
    Follow.query.filter_by(follower_id=current_user.id, followed_id=target.id).delete()
    db.session.commit()
    flash(f"Unfollowed {target.username}.", "info")
    return redirect(url_for("profiles.public_profile", username=username))


@social_bp.route("/u/<username>/followers")
def followers_list(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    followers = (
        User.query.join(Follow, Follow.follower_id == User.id)
        .filter(Follow.followed_id == profile_user.id)
        .order_by(User.username)
        .all()
    )
    return render_template(
        "social/user_list.html", profile_user=profile_user, users=followers, heading="Followers"
    )


@social_bp.route("/u/<username>/following")
def following_list(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    following = (
        User.query.join(Follow, Follow.followed_id == User.id)
        .filter(Follow.follower_id == profile_user.id)
        .order_by(User.username)
        .all()
    )
    return render_template(
        "social/user_list.html", profile_user=profile_user, users=following, heading="Following"
    )


# --- friends -----------------------------------------------------------


@social_bp.route("/u/<username>/friends")
def friends_list(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    friend_ids = Friendship.friend_ids_for(profile_user.id)
    friends = (
        User.query.filter(User.id.in_(friend_ids)).order_by(User.username).all()
        if friend_ids
        else []
    )
    return render_template(
        "social/user_list.html", profile_user=profile_user, users=friends, heading="Friends"
    )


@social_bp.route("/u/<username>/friend-request", methods=["POST"])
@login_required
@limiter.limit("20 per hour", methods=["POST"])
def send_friend_request(username):
    receiver = User.query.filter_by(username=username).first_or_404()

    if receiver.id == current_user.id:
        flash("You can't send yourself a friend request.", "danger")
        return redirect(url_for("profiles.public_profile", username=username))

    if Friendship.are_friends(current_user.id, receiver.id):
        flash("You're already friends.", "info")
        return redirect(url_for("profiles.public_profile", username=username))

    existing = FriendRequest.query.filter(
        FriendRequest.status == FriendRequestStatus.PENDING,
        or_(
            and_(
                FriendRequest.sender_id == current_user.id,
                FriendRequest.receiver_id == receiver.id,
            ),
            and_(
                FriendRequest.sender_id == receiver.id,
                FriendRequest.receiver_id == current_user.id,
            ),
        ),
    ).first()
    if existing is not None:
        flash("A friend request is already pending between you two.", "info")
        return redirect(url_for("profiles.public_profile", username=username))

    friend_request = FriendRequest(sender_id=current_user.id, receiver_id=receiver.id)
    db.session.add(friend_request)
    db.session.flush()  # assign friend_request.id before it's used as a notification target
    NotificationService.notify(
        recipient_id=receiver.id,
        actor_id=current_user.id,
        type=NotificationType.FRIEND_REQUEST,
        target_type="friend_request",
        target_id=friend_request.id,
    )
    db.session.commit()
    flash("Friend request sent.", "success")
    return redirect(url_for("profiles.public_profile", username=username))


@social_bp.route("/friend-requests")
@login_required
def friend_requests():
    incoming = (
        FriendRequest.query.filter_by(receiver_id=current_user.id, status=FriendRequestStatus.PENDING)
        .order_by(FriendRequest.created_at.desc())
        .all()
    )
    outgoing = (
        FriendRequest.query.filter_by(sender_id=current_user.id, status=FriendRequestStatus.PENDING)
        .order_by(FriendRequest.created_at.desc())
        .all()
    )
    return render_template("social/friend_requests.html", incoming=incoming, outgoing=outgoing)


@social_bp.route("/friend-requests/<uuid:request_id>/accept", methods=["POST"])
@login_required
def accept_friend_request(request_id):
    friend_request = FriendRequest.query.get_or_404(request_id)
    require_ownership(friend_request.receiver_id)
    if friend_request.status != FriendRequestStatus.PENDING:
        abort(404)

    friend_request.status = FriendRequestStatus.ACCEPTED
    friend_request.responded_at = datetime.now(timezone.utc)
    db.session.add(Friendship.create_for_pair(friend_request.sender_id, friend_request.receiver_id))
    db.session.commit()
    flash(f"You are now friends with {friend_request.sender.username}.", "success")
    return redirect(url_for("social.friend_requests"))


@social_bp.route("/friend-requests/<uuid:request_id>/decline", methods=["POST"])
@login_required
def decline_friend_request(request_id):
    friend_request = FriendRequest.query.get_or_404(request_id)
    require_ownership(friend_request.receiver_id)
    if friend_request.status != FriendRequestStatus.PENDING:
        abort(404)

    friend_request.status = FriendRequestStatus.DECLINED
    friend_request.responded_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Friend request declined.", "info")
    return redirect(url_for("social.friend_requests"))


@social_bp.route("/friend-requests/<uuid:request_id>/cancel", methods=["POST"])
@login_required
def cancel_friend_request(request_id):
    friend_request = FriendRequest.query.get_or_404(request_id)
    require_ownership(friend_request.sender_id)
    if friend_request.status != FriendRequestStatus.PENDING:
        abort(404)

    db.session.delete(friend_request)
    db.session.commit()
    flash("Friend request canceled.", "info")
    return redirect(url_for("social.friend_requests"))


@social_bp.route("/u/<username>/unfriend", methods=["POST"])
@login_required
def unfriend(username):
    other = User.query.filter_by(username=username).first_or_404()
    low, high = Friendship.normalize_pair(current_user.id, other.id)
    Friendship.query.filter_by(user_low_id=low, user_high_id=high).delete()
    db.session.commit()
    flash(f"You are no longer friends with {other.username}.", "info")
    return redirect(url_for("profiles.public_profile", username=username))


# --- feed --------------------------------------------------------------


@social_bp.route("/feed")
@login_required
def feed():
    page = request.args.get("page", 1, type=int)

    followed_ids = select(Follow.followed_id).where(Follow.follower_id == current_user.id)
    friend_ids = Friendship.friend_ids_for(current_user.id)

    query = (
        # Friendship doesn't imply a Follow row (accepting a friend request
        # never creates one — see social.accept_friend_request) and vice
        # versa, so the feed has to union both: a friend's memory should
        # show up here even if you never separately hit Follow on them.
        Memory.query.filter(
            or_(Memory.user_id.in_(followed_ids), Memory.user_id.in_(friend_ids))
        )
        # Performance/defense-in-depth pre-filter: never even fetch private
        # memories into the feed. can_view_memory below is still the
        # authoritative check for the friends-only case.
        .filter(Memory.visibility != MemoryVisibility.PRIVATE)
        .options(joinedload(Memory.user), selectinload(Memory.media))
        .order_by(Memory.created_at.desc())
    )
    pagination = db.paginate(query, page=page, per_page=FEED_PER_PAGE, error_out=False)
    # can_view_memory is the single source of truth — every row still goes
    # through it here. A followed-but-not-friended user's friends-only
    # memory is dropped at this point, so a page can come back with fewer
    # than FEED_PER_PAGE items; that's an accepted trade-off for never
    # leaking content via a SQL-only visibility filter.
    pagination.items = [m for m in pagination.items if can_view_memory(current_user, m)]

    upcoming_friend_concerts = []
    if friend_ids:
        upcoming_friend_concerts = (
            db.session.query(Concert)
            .join(Attendance, Attendance.concert_id == Concert.id)
            .filter(Attendance.user_id.in_(friend_ids))
            .filter(Concert.starts_at > datetime.now(timezone.utc))
            .distinct()
            .order_by(Concert.starts_at)
            .all()
        )

    like_counts = MemoryLike.counts_for([m.id for m in pagination.items])

    return render_template(
        "social/feed.html",
        pagination=pagination,
        memories=pagination.items,
        like_counts=like_counts,
        upcoming_friend_concerts=upcoming_friend_concerts,
    )


# --- notifications -----------------------------------------------------


@social_bp.route("/notifications")
@login_required
def notifications():
    items = (
        Notification.query.filter_by(recipient_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    rendered = [
        (notification, render_notification(notification), notification_url(notification))
        for notification in items
    ]
    return render_template("social/notifications.html", notifications=rendered)


@social_bp.route("/notifications/<uuid:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    require_ownership(notification.recipient_id)

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.session.commit()
    return redirect(notification_url(notification))


@social_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    # Self-scoped by current_user.id, not a caller-supplied id — no IDOR
    # surface to guard here, unlike the single-notification route above.
    Notification.query.filter_by(recipient_id=current_user.id, read_at=None).update(
        {"read_at": datetime.now(timezone.utc)}
    )
    db.session.commit()
    flash("All notifications marked as read.", "info")
    return redirect(url_for("social.notifications"))
