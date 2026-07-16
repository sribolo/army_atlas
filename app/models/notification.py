"""A notification pointing at a comment, like, follow, friend request, or
message.

recipient_id/actor_id are real foreign keys. target_type/target_id are a
generic pointer with no database-level foreign key — app.notifications
(NotificationService and render_notification) owns resolving that pointer
and rendering gracefully if the target has been deleted.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class NotificationType(str, enum.Enum):
    COMMENT = "comment"
    LIKE = "like"
    FOLLOW = "follow"
    FRIEND_REQUEST = "friend_request"
    MESSAGE = "message"


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type: Mapped[NotificationType] = mapped_column(
        # values_callable: persist the enum values ("comment", "like", ...),
        # not SQLAlchemy's default of the enum member names.
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])
    actor: Mapped["User"] = relationship(foreign_keys=[actor_id])

    def __init__(
        self,
        *,
        recipient_id: uuid.UUID,
        actor_id: uuid.UUID,
        type: NotificationType,
        target_type: str,
        target_id: uuid.UUID,
    ) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(recipient_id=recipient_id, actor_id=actor_id, type=type, target_type=target_type, target_id=target_id)  # type: ignore[call-arg]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __repr__(self):
        return f"<Notification {self.type.value} to={self.recipient_id} from={self.actor_id}>"
