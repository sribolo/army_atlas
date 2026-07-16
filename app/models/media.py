"""Photos and videos attached to a memory, stored in Cloudinary.

Only the Cloudinary url/public_id are kept here — see
app/blueprints/memories/media.py for upload validation and
app/uploads.py for the shared content-based checks.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.memory import Memory


class MediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class Media(db.Model):
    __tablename__ = "media"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    url: Mapped[str] = mapped_column(String(500), nullable=False)
    public_id: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(
        # values_callable: persist "image"/"video" (the enum values), not
        # SQLAlchemy's default of "IMAGE"/"VIDEO" (the enum member names).
        Enum(MediaType, name="media_type", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    memory: Mapped["Memory"] = relationship(back_populates="media")  # noqa: F821

    def __init__(
        self, *, memory_id: uuid.UUID, url: str, public_id: str, media_type: MediaType
    ) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(memory_id=memory_id, url=url, public_id=public_id, media_type=media_type)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Media {self.media_type.value} {self.public_id}>"
