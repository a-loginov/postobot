from __future__ import annotations

import config
from database.models import Request, RequestStatus, User
from database.repositories.requests import RequestRepository
from database.repositories.users import UserRepository


class RequestValidationError(Exception):
    """Raised when request data fails validation."""


MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 128
MAX_CLASS_LENGTH = 32
MAX_REASON_LENGTH = 1000


class RequestService:
    def __init__(
        self,
        request_repo: RequestRepository,
        user_repo: UserRepository,
    ) -> None:
        self._request_repo = request_repo
        self._user_repo = user_repo

    @staticmethod
    def validate_full_name(value: str) -> str:
        value = value.strip()
        if not value:
            raise RequestValidationError("Имя и фамилия обязательны.")
        if len(value) < MIN_NAME_LENGTH:
            raise RequestValidationError("Имя и фамилия должны содержать минимум 2 символа.")
        if len(value) > MAX_NAME_LENGTH:
            raise RequestValidationError(f"Имя и фамилия не должны превышать {MAX_NAME_LENGTH} символов.")
        return value

    @staticmethod
    def validate_class_name(value: str) -> str:
        value = value.strip()
        if not value:
            raise RequestValidationError("Класс обязателен.")
        if len(value) > MAX_CLASS_LENGTH:
            raise RequestValidationError(f"Класс не должен превышать {MAX_CLASS_LENGTH} символов.")
        return value

    @staticmethod
    def validate_reason(value: str) -> str:
        value = value.strip()
        if not value:
            raise RequestValidationError("Причина обязательна.")
        if len(value) > MAX_REASON_LENGTH:
            raise RequestValidationError(f"Причина не должна превышать {MAX_REASON_LENGTH} символов.")
        return value

    @staticmethod
    def validate_photo(photo_file_id: str | None) -> str:
        if not photo_file_id:
            raise RequestValidationError("Необходимо прикрепить фотографию проблемы.")
        return photo_file_id

    def create_request(
        self,
        user: User,
        full_name: str,
        class_name: str,
        reason: str,
        photo_file_id: str,
    ) -> Request:
        full_name = self.validate_full_name(full_name)
        class_name = self.validate_class_name(class_name)
        reason = self.validate_reason(reason)
        photo_file_id = self.validate_photo(photo_file_id)
        return self._request_repo.create(
            user=user,
            full_name=full_name,
            class_name=class_name,
            reason=reason,
            photo_file_id=photo_file_id,
        )

    def get_request(self, request_id: int) -> Request:
        request = self._request_repo.get_or_404(request_id)
        return request

    def get_user_requests(self, user: User) -> list[Request]:
        return self._request_repo.list_by_user(user)

    def get_new_requests(self) -> list[Request]:
        return self._request_repo.list_by_status(RequestStatus.NEW)

    def update_status(self, request_id: int, status: RequestStatus) -> Request:
        return self._request_repo.update_status(request_id, status)

    def list_admin_ids(self) -> list[int]:
        """Return telegram ids of all registered ADMIN users from DB."""
        admins = self._user_repo.list_admins()
        return [a.telegram_id for a in admins]
