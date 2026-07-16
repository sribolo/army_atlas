"""Confirmed friendships. Always stored with the smaller user id first
(user_low_id < user_high_id) so a pair can never be represented twice —
that ordering *is* the (a, b)/(b, a) uniqueness constraint.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Friendship(db.Model):
    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user_low_id < user_high_id", name="ck_friendships_ordered_pair"),
    )

    user_low_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, *, user_low_id: uuid.UUID, user_high_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(user_low_id=user_low_id, user_high_id=user_high_id)  # type: ignore[call-arg]

    @staticmethod
    def normalize_pair(user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
        """Return (low, high) — the canonical column order for a pair."""
        return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)

    @classmethod
    def create_for_pair(cls, user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> "Friendship":
        low, high = cls.normalize_pair(user_a_id, user_b_id)
        return cls(user_low_id=low, user_high_id=high)

    @classmethod
    def are_friends(cls, user_a_id: uuid.UUID, user_b_id: uuid.UUID) -> bool:
        """Answers "are X and Y friends" — the other required helper."""
        low, high = cls.normalize_pair(user_a_id, user_b_id)
        return (
            db.session.query(cls.user_low_id)
            .filter(cls.user_low_id == low, cls.user_high_id == high)
            .first()
            is not None
        )

    @classmethod
    def friend_ids_for(cls, user_id: uuid.UUID) -> list[uuid.UUID]:
        """All user ids this user is friends with, regardless of which
        column side they landed on when the pair was normalized.
        """
        as_low = db.session.query(cls.user_high_id).filter(cls.user_low_id == user_id)
        as_high = db.session.query(cls.user_low_id).filter(cls.user_high_id == user_id)
        return [row[0] for row in as_low.union(as_high).all()]

    def __repr__(self):
        return f"<Friendship {self.user_low_id} <-> {self.user_high_id}>"
