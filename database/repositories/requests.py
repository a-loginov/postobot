import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Request, RequestStatus, User

logger = logging.getLogger(__name__)


class RequestNotFoundError(Exception):
    """Raised when a request cannot be found."""


class RequestRepositoryError(Exception):
    """Base error for the request repository."""


class RequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, request_id: int) -> Request | None:
        return self._session.get(Request, request_id)

    def get_or_404(self, request_id: int) -> Request:
        request = self.get(request_id)
        if request is None:
            raise RequestNotFoundError(f"Request {request_id} not found")
        return request

    def create(
        self,
        user: User,
        full_name: str,
        class_name: str,
        reason: str,
        photo_file_id: str,
        status: RequestStatus = RequestStatus.NEW,
    ) -> Request:
        try:
            request = Request(
                user_id=user.id,
                full_name=full_name,
                class_name=class_name,
                reason=reason,
                photo_file_id=photo_file_id,
                status=status,
            )
            self._session.add(request)
            self._session.flush()
            return request
        except Exception as exc:
            self._session.rollback()
            user_id = getattr(user, "id", None)
            logger.exception("Failed to create request for user_id=%s", user_id)
            raise RequestRepositoryError("Не удалось создать заявку") from exc

    def list_by_user(self, user: User) -> list[Request]:
        stmt = (
            select(Request)
            .where(Request.user_id == user.id)
            .order_by(Request.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def list_by_status(self, status: RequestStatus) -> list[Request]:
        stmt = (
            select(Request)
            .where(Request.status == status)
            .order_by(Request.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def list_all(self) -> list[Request]:
        stmt = select(Request).order_by(Request.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def update_status(self, request_id: int, status: RequestStatus) -> Request:
        request = self.get_or_404(request_id)
        try:
            request.status = status
            self._session.flush()
        except Exception as exc:
            self._session.rollback()
            logger.exception("Failed to update status for request_id=%s", request_id)
            raise RequestRepositoryError("Не удалось изменить статус заявки") from exc
        return request
