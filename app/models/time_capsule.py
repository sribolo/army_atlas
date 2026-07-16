"""A private, time-locked message to your future self.

The body is never served to anyone — including the owner — before
unlock_at, and owner-only after (see app.authorization.require_ownership
and the routes in app/blueprints/profiles/routes.py). is_unlocked is the
single place that decision is made; call sites should check it rather than
comparing timestamps themselves.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class TimeCapsule(db.Model):
    __tablename__ = "time_capsules"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    unlock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship()

    def __init__(self, *, user_id: uuid.UUID, body: str, unlock_at: datetime) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(user_id=user_id, body=body, unlock_at=unlock_at)  # type: ignore[call-arg]

    @property
    def _unlock_at_utc(self) -> datetime:
        """unlock_at with tzinfo guaranteed present — SQLite (used for
        local dev without Postgres) returns naive datetimes even from a
        timezone-aware column.
        """
        unlock_at = self.unlock_at
        if unlock_at.tzinfo is None:
            unlock_at = unlock_at.replace(tzinfo=timezone.utc)
        return unlock_at

    @property
    def is_unlocked(self) -> bool:
        return datetime.now(timezone.utc) >= self._unlock_at_utc

    @property
    def unlock_at_utc_iso(self) -> str:
        """UTC ISO 8601 string with an explicit offset, for the countdown
        timer's data attribute — see Concert.starts_at_utc_iso for why the
        explicit offset matters.
        """
        return self._unlock_at_utc.isoformat()

    def __repr__(self):
        return f"<TimeCapsule {self.id} unlock_at={self.unlock_at}>"