from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.language import Language

ROLE_FARMER = "farmer"
ROLE_ADMIN = "admin"


class User(TimestampMixin, Base):
    """Every person who logs in. `role` decides access (farmer or admin)."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('farmer', 'admin')", name="role_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default=ROLE_FARMER, server_default=ROLE_FARMER)
    preferred_language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="RESTRICT"))
    state: Mapped[str | None] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(80))
    village: Mapped[str | None] = mapped_column(String(80))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    primary_crops: Mapped[str | None] = mapped_column(String(255))  # comma-separated, e.g. "paddy,chilli"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    preferred_language: Mapped[Language] = relationship(lazy="joined")
    admin_profile: Mapped["Admin | None"] = relationship(back_populates="user", uselist=False)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


class Admin(TimestampMixin, Base):
    """Extra details for admin accounts (one-to-one with users).

    The `users.role` column is what grants access; this table records who
    the admin is and what they manage, as the spec's separate admins table.
    """

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    designation: Mapped[str | None] = mapped_column(String(120))
    can_manage_users: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    can_manage_documents: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    user: Mapped[User] = relationship(back_populates="admin_profile")
