"""Friend requests: the pending/accepted/declined lifecycle between two
users. Accepting a request creates the normalized Friendship row (see
app/models/friendship.py) and marks this row accepted — it's kept as
history, not deleted. Canceling a still-pending request deletes it instead,
since a canceled request has no history value.

Rejecting a duplicate pending request between the same pair (in either
direction) is enforced at the application level in
app/blueprints/social/routes.py, not as a DB constraint — a symmetric
"one pending row per unordered pair" rule doesn't map cleanly onto a
portable column-level constraint the way the self-request check does.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class FriendRequestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class FriendRequest(db.Model):
    __tablename__ = "friend_requests"
    __table_args__ = (
        CheckConstraint("sender_id != receiver_id", name="ck_friend_requests_no_self_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[FriendRequestStatus] = mapped_column(
        # values_callable: persist "pending"/"accepted"/"declined" (the enum
        # values), not SQLAlchemy's default of the enum member names.
        Enum(
            FriendRequestStatus,
            name="friend_request_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=FriendRequestStatus.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship(foreign_keys=[receiver_id])

    def __init__(self, *, sender_id: uuid.UUID, receiver_id: uuid.UUID) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(sender_id=sender_id, receiver_id=receiver_id)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<FriendRequest {self.sender_id} -> {self.receiver_id} ({self.status.value})>"
