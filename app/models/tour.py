"""The tours table — a named collection of concert dates."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.concert import Concert


class Tour(db.Model):
    __tablename__ = "tours"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    concerts: Mapped[list["Concert"]] = relationship(
        back_populates="tour", order_by="Concert.starts_at"
    )

    def __init__(self, *, name: str) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(name=name)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Tour {self.name}>"
