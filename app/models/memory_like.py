"""Likes on memories. Table is memory_likes, never `like` — reserved word.

Unique on (user_id, memory_id) prevents double-likes.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class MemoryLike(db.Model):
    __tablename__ = "memory_likes"

    # Composite primary key: a user likes a given memory at most once. This
    # *is* the (user_id, memory_id) uniqueness constraint.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __init__(self, *, user_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(user_id=user_id, memory_id=memory_id)  # type: ignore[call-arg]

    @classmethod
    def counts_for(cls, memory_ids) -> dict:
        """Bulk like-count lookup for a list of memory ids — one grouped
        query instead of N+1 when rendering a list of memories.
        """
        if not memory_ids:
            return {}
        return dict(
            db.session.query(cls.memory_id, db.func.count(cls.user_id))
            .filter(cls.memory_id.in_(memory_ids))
            .group_by(cls.memory_id)
            .all()
        )

    def __repr__(self):
        return f"<MemoryLike user={self.user_id} memory={self.memory_id}>"
