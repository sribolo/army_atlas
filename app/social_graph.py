"""Cross-blueprint social graph reads: memory visibility and follow/friend
relationship state. Shared by profiles, concerts, memories, and social —
none of those blueprints should contain their own visibility logic.
"""

from sqlalchemy import and_, or_

from app.models import Follow, FriendRequest, FriendRequestStatus, Friendship, MemoryVisibility


def can_view_memory(viewer, memory) -> bool:
    """The single source of truth for who may see a memory.

    public: everyone. private: the owner only. friends: the owner and
    confirmed friends only. Call this everywhere a memory is listed or
    shown — feed, profile, concert page, memory detail. No visibility
    logic should exist anywhere else.
    """
    if memory.visibility == MemoryVisibility.PUBLIC:
        return True

    if not getattr(viewer, "is_authenticated", False):
        return False

    if viewer.id == memory.user_id:
        return True

    if memory.visibility == MemoryVisibility.FRIENDS:
        return Friendship.are_friends(viewer.id, memory.user_id)

    return False  # private, and viewer isn't the owner


def relationship_summary(viewer, other_user):
    """Follow/friend state between `viewer` and `other_user`, for rendering
    profile action buttons (follow, send/cancel/accept/decline request,
    unfriend). All fields are False/None for an anonymous or self viewer.
    """
    if not getattr(viewer, "is_authenticated", False) or viewer.id == other_user.id:
        return {"is_following": False, "are_friends": False, "pending_request": None}

    is_following = (
        Follow.query.filter_by(follower_id=viewer.id, followed_id=other_user.id).first()
        is not None
    )
    are_friends = Friendship.are_friends(viewer.id, other_user.id)

    pending_request = None
    if not are_friends:
        row = FriendRequest.query.filter(
            FriendRequest.status == FriendRequestStatus.PENDING,
            or_(
                and_(
                    FriendRequest.sender_id == viewer.id,
                    FriendRequest.receiver_id == other_user.id,
                ),
                and_(
                    FriendRequest.sender_id == other_user.id,
                    FriendRequest.receiver_id == viewer.id,
                ),
            ),
        ).first()
        if row is not None:
            pending_request = {
                "id": row.id,
                "direction": "sent" if row.sender_id == viewer.id else "received",
            }

    return {
        "is_following": is_following,
        "are_friends": are_friends,
        "pending_request": pending_request,
    }
