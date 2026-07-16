"""A user-filed report against a memory, comment, or user, reviewed by an
admin (see app/blueprints/admin/routes.py).

target_type/target_id are a generic pointer with no database-level foreign
key — same pattern as Notification. The admin review queue owns resolving
that pointer.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class Report(db.Model):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ReportStatus] = mapped_column(
        # values_callable: persist "open"/"resolved" (the enum values), not
        # SQLAlchemy's default of the enum member names.
        Enum(
            ReportStatus, name="report_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]
        ),
        nullable=False,
        default=ReportStatus.OPEN,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    reporter: Mapped["User"] = relationship()

    def __init__(self, *, reporter_id: uuid.UUID, target_type: str, target_id: uuid.UUID, reason: str) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(reporter_id=reporter_id, target_type=target_type, target_id=target_id, reason=reason)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Report {self.target_type}:{self.target_id} ({self.status.value})>"