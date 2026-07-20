import datetime
import enum

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Role(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[Role] = mapped_column(
        # values_callable stores "user"/"admin" (value), not "USER"/"ADMIN" (name).
        # ponytail: native_enum=False (VARCHAR+CHECK) so adding a role never needs ALTER TYPE.
        Enum(Role, native_enum=False, length=20, values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        default=Role.USER,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    verification_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    verification_code_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r}, role={self.role})"
