"""The users table. Named `users`, never `user` — reserved in PostgreSQL."""

import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    display_name: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    bias: Mapped[str | None] = mapped_column(String(50))
    bio: Mapped[str | None] = mapped_column(Text)

    profile_image_url: Mapped[str | None] = mapped_column(String(500))
    profile_image_public_id: Mapped[str | None] = mapped_column(String(255))
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    cover_image_public_id: Mapped[str | None] = mapped_column(String(255))

    instagram: Mapped[str | None] = mapped_column(String(100))
    tiktok: Mapped[str | None] = mapped_column(String(100))
    twitter: Mapped[str | None] = mapped_column(String(100))
    discord: Mapped[str | None] = mapped_column(String(100))
    spotify: Mapped[str | None] = mapped_column(String(100))

    # Shadows UserMixin's default is_active=True property with a real column.
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(self, *, username: str, email: str, password_hash: str) -> None:
        # Spelled out explicitly so type checkers see a real constructor.
        # Flask-SQLAlchemy synthesizes db.Model's base dynamically via
        # types.new_class(), which Pyright can't trace through, so without
        # this it infers a zero-argument __init__ from object and flags
        # every keyword argument below as unknown. Other columns (country,
        # bio, is_admin, ...) are optional and set via normal attribute
        # assignment after construction, same as before.
        super().__init__(username=username, email=email, password_hash=password_hash)  # type: ignore[call-arg]

    def __repr__(self):
        return f"<User {self.username}>"
