"""A memory: a user's own content attached to a canonical concert.

A memory references its concert by foreign key only — name, tour, venue,
city, country, and date all come from Concert. Never duplicate those onto
this table; Concert is the single source of truth for that data.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.tag import memory_tags

if TYPE_CHECKING:
    from app.models.concert import Concert
    from app.models.media import Media
    from app.models.tag import Tag
    from app.models.user import User


class MemoryVisibility(str, enum.Enum):
    PUBLIC = "public"
    FRIENDS = "friends"
    PRIVATE = "private"


class Memory(db.Model):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concert_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    seat_section: Mapped[str | None] = mapped_column(String(100))
    story: Mapped[str | None] = mapped_column(Text)

    visibility: Mapped[MemoryVisibility] = mapped_column(
        # values_callable: persist "public"/"friends"/"private" (the enum
        # values), not SQLAlchemy's default of "PUBLIC"/"FRIENDS"/"PRIVATE"
        # (the enum member names).
        Enum(MemoryVisibility, name="memory_visibility", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        default=MemoryVisibility.PUBLIC,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    concert: Mapped["Concert"] = relationship()
    user: Mapped["User"] = relationship()
    media: Mapped[list["Media"]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", order_by="Media.created_at"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=memory_tags, order_by="Tag.name")

    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        concert_id: uuid.UUID,
        title: str,
        seat_section: str | None = None,
        story: str | None = None,
        visibility: MemoryVisibility = MemoryVisibility.PUBLIC,
    ) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(user_id=user_id, concert_id=concert_id, title=title, seat_section=seat_section, story=story, visibility=visibility)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Memory {self.title!r} by user={self.user_id}>"
