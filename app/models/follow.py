"""Who follows whom — one-directional, no approval needed. Distinct from
friendship (app/models/friendship.py), which is mutual and request-based.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Follow(db.Model):
    __tablename__ = "follows"
    __table_args__ = (
        CheckConstraint("follower_id != followed_id", name="ck_follows_no_self_follow"),
    )

    # Composite primary key: a user follows another user at most once. This
    # *is* the (follower_id, followed_id) uniqueness constraint.
    follower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, *, follower_id: uuid.UUID, followed_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(follower_id=follower_id, followed_id=followed_id)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Follow {self.follower_id} -> {self.followed_id}>"
