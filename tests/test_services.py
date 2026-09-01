import pytest

from database.models import RequestStatus, User, UserRole
from database.repositories.requests import RequestRepository
from database.repositories.users import UserRepository
from services.request_service import (
    MAX_CLASS_LENGTH,
    MAX_NAME_LENGTH,
    MAX_REASON_LENGTH,
    RequestService,
    RequestValidationError,
)


def _make_user(db_session) -> User:
    return UserRepository(db_session).create(
        telegram_id=200, username="test", full_name="Тестов Тест", role=UserRole.USER
    )


# --- Валидация ФИО ---

def test_full_name_valid():
    assert RequestService.validate_full_name("  Иванов Иван  ") == "Иванов Иван"


def test_full_name_empty():
    with pytest.raises(RequestValidationError):
        RequestService.validate_full_name("   ")


def test_full_name_too_short():
    with pytest.raises(RequestValidationError):
        RequestService.validate_full_name("И")


def test_full_name_too_long():
    with pytest.raises(RequestValidationError):
        RequestService.validate_full_name("И" * (MAX_NAME_LENGTH + 1))


# --- Валидация класса ---

def test_class_valid():
    assert RequestService.validate_class_name("10А") == "10А"


def test_class_empty():
    with pytest.raises(RequestValidationError):
        RequestService.validate_class_name(" ")


def test_class_too_long():
    with pytest.raises(RequestValidationError):
        RequestService.validate_class_name("К" * (MAX_CLASS_LENGTH + 1))


# --- Валидация причины ---

def test_reason_valid():
    assert RequestService.validate_reason("  Не работает экран  ") == "Не работает экран"


def test_reason_empty():
    with pytest.raises(RequestValidationError):
        RequestService.validate_reason("")


def test_reason_too_long():
    with pytest.raises(RequestValidationError):
        RequestService.validate_reason("Р" * (MAX_REASON_LENGTH + 1))


# --- Валидация фото ---

def test_photo_required():
    with pytest.raises(RequestValidationError):
        RequestService.validate_photo(None)


def test_photo_required_empty_string():
    with pytest.raises(RequestValidationError):
        RequestService.validate_photo("")


def test_photo_valid():
    assert RequestService.validate_photo("file_id_abc") == "file_id_abc"


# --- Создание заявки через сервис ---

def test_create_request_via_service(db_session):
    user = _make_user(db_session)
    db_session.flush()
    service = RequestService(
        RequestRepository(db_session), UserRepository(db_session)
    )
    request = service.create_request(
        user=user,
        full_name="Иванов Иван",
        class_name="10А",
        reason="Не работает экран в кабинете информатики.",
        photo_file_id="file_id_1",
    )
    db_session.flush()
    assert request.id is not None
    assert request.status == RequestStatus.NEW


def test_create_request_rejects_without_photo(db_session):
    user = _make_user(db_session)
    db_session.flush()
    service = RequestService(
        RequestRepository(db_session), UserRepository(db_session)
    )
    with pytest.raises(RequestValidationError):
        service.create_request(
            user=user,
            full_name="Иванов Иван",
            class_name="10А",
            reason="Причина",
            photo_file_id="",
        )


def test_get_user_requests(db_session):
    user = _make_user(db_session)
    db_session.flush()
    service = RequestService(
        RequestRepository(db_session), UserRepository(db_session)
    )
    r1 = service.create_request(user=user, full_name="Иванов", class_name="10А",
                                reason="Р1", photo_file_id="f1")
    r2 = service.create_request(user=user, full_name="Иванов", class_name="10А",
                                reason="Р2", photo_file_id="f2")
    db_session.flush()
    results = service.get_user_requests(user)
    assert {r.id for r in results} == {r1.id, r2.id}


def test_change_status_via_service(db_session):
    user = _make_user(db_session)
    db_session.flush()
    service = RequestService(
        RequestRepository(db_session), UserRepository(db_session)
    )
    request = service.create_request(
        user=user, full_name="Иванов", class_name="10А",
        reason="Р", photo_file_id="f1",
    )
    db_session.flush()
    updated = service.update_status(request.id, RequestStatus.COMPLETED)
    db_session.flush()
    assert updated.status == RequestStatus.COMPLETED
