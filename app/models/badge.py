"""The badge catalog. Seeded from app/data/badges.json via `flask
seed-badges` — no user-facing or admin write path creates a Badge row.
"""

import uuid

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Badge(db.Model):
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, *, code: str, name: str, icon: str, description: str) -> None:
        # See User.__init__ (app/models/user.py) for why this is spelled
        # out explicitly rather than relying on the dynamically generated
        # declarative constructor.
        super().__init__(code=code, name=name, icon=icon, description=description)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<Badge {self.code}>"