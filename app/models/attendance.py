"""Who attended which concert — the source of truth for attended counts and
passport stamps. Never derive those from memories; a memory is optional
commentary, attendance is the fact.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Attendance(db.Model):
    __tablename__ = "attendance"

    # Composite primary key: a user attends a given concert at most once.
    # This *is* the (user_id, concert_id) uniqueness constraint.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    concert_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), primary_key=True
    )

    # Opt-in to appear in the concert's "find ARMY who attended this" list
    # (app/blueprints/concerts/routes.py). Off by default — never list a
    # user who hasn't explicitly opted in.
    open_to_connect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seat: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(self, *, user_id: uuid.UUID, concert_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(user_id=user_id, concert_id=concert_id)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Attendance user={self.user_id} concert={self.concert_id}>"
