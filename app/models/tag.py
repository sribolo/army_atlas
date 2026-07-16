"""Tags and the memory_tags many-to-many join table.

Tag names are always stored lowercase with no leading '#' — normalization
happens once, in app/blueprints/memories/forms.py's parse_tags(), before a
Tag row is ever created or looked up.
"""

import uuid

from sqlalchemy import Column, ForeignKey, String, Table, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db

memory_tags = Table(
    "memory_tags",
    db.metadata,
    Column(
        "memory_id",
        Uuid(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        Uuid(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(db.Model):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    def __init__(self, *, name: str) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(name=name)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Tag {self.name}>"
