import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import User, UserRole

logger = logging.getLogger(__name__)


class UserRepositoryError(Exception):
    """Base error for the user repository."""


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        return self._session.scalar(stmt)

    def create(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role=role,
        )
        try:
            self._session.add(user)
            self._session.flush()
        except Exception as exc:
            self._session.rollback()
            logger.exception("Failed to create user telegram_id=%s", telegram_id)
            raise UserRepositoryError("Не удалось создать пользователя") from exc
        return user

    def get_or_create(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        user = self.get_by_telegram_id(telegram_id)
        if user is None:
            user = self.create(telegram_id, username, full_name, role)
        return user

    def list_admins(self) -> list[User]:
        stmt = select(User).where(User.role == UserRole.ADMIN)
        return list(self._session.scalars(stmt).all())
