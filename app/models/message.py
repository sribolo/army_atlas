"""Direct messages between two users.

A conversation is not its own table — it's rendered by querying messages in
both directions between two user ids, ordered by created_at (see
app/blueprints/messages/routes.py). A dedicated Conversation table is the
future upgrade path for group DMs only; a 1:1 thread doesn't need one.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class Message(db.Model):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    image_public_id: Mapped[str | None] = mapped_column(String(255))

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])

    def __init__(
        self,
        *,
        sender_id: uuid.UUID,
        recipient_id: uuid.UUID,
        body: str,
        image_url: str | None = None,
        image_public_id: str | None = None,
    ) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(sender_id=sender_id, recipient_id=recipient_id, body=body, image_url=image_url, image_public_id=image_public_id)  # type: ignore[call-arg]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __repr__(self):
        return f"<Message {self.sender_id} -> {self.recipient_id}>"