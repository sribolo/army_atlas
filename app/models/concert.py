"""The concerts table — admin-curated canonical concert data.

starts_at is always stored in UTC; `timezone` holds the IANA zone name for
the venue so local time can be reconstructed (starts_at_local) without
losing precision to a fixed UTC offset.
"""

import uuid
from datetime import datetime, timezone as dt_timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.tour import Tour


class Concert(db.Model):
    __tablename__ = "concerts"
    __table_args__ = (
        # Natural key used by `flask seed-concerts` to upsert idempotently.
        UniqueConstraint(
            "tour_id", "venue", "starts_at", name="uq_concerts_tour_venue_starts_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tour_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tours.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    venue: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(dt_timezone.utc),
    )

    tour: Mapped["Tour"] = relationship(back_populates="concerts")

    def __init__(self, *, tour_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly. The remaining required fields (name, venue, ...)
        # are set via normal attribute assignment by the caller before the
        # session is flushed — see app/cli.py's seed_concerts.
        super().__init__(tour_id=tour_id)  # type: ignore[call-arg]

    @property
    def _starts_at_utc(self) -> datetime:
        """starts_at with tzinfo guaranteed present (see starts_at_local's
        docstring for why: SQLite returns naive datetimes even from a
        timezone-aware column).
        """
        starts_at = self.starts_at
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=dt_timezone.utc)
        return starts_at

    @property
    def starts_at_local(self) -> datetime:
        """starts_at converted to the venue's local timezone."""
        return self._starts_at_utc.astimezone(ZoneInfo(self.timezone))

    @property
    def starts_at_utc_iso(self) -> str:
        """UTC ISO 8601 string with an explicit offset, for the client-side
        countdown timer's data attribute (see app/static/js/countdown.js) —
        without an explicit offset, JavaScript's Date parser would assume
        the browser's local timezone instead of UTC.
        """
        return self._starts_at_utc.isoformat()

    @property
    def is_upcoming(self) -> bool:
        return self._starts_at_utc > datetime.now(dt_timezone.utc)

    def __repr__(self):
        return f"<Concert {self.name} @ {self.venue}>"
