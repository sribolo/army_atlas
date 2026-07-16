"""Which users have earned which badges. Unique on (user_id, badge_id) —
BadgeService (app/badges.py) relies on this to award idempotently: it just
tries the insert and the constraint makes re-evaluation safe.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.badge import Badge


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    # Composite primary key: a user earns a given badge at most once. This
    # *is* the (user_id, badge_id) uniqueness constraint.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    badge: Mapped["Badge"] = relationship()

    def __init__(self, *, user_id: uuid.UUID, badge_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(user_id=user_id, badge_id=badge_id)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<UserBadge user={self.user_id} badge={self.badge_id}>"