import pytest

from database.models import Request, RequestStatus, User, UserRole
from database.repositories.requests import (
    RequestNotFoundError,
    RequestRepository,
    RequestRepositoryError,
)
from database.repositories.users import UserRepository, UserRepositoryError


def _make_user(db_session) -> User:
    repo = UserRepository(db_session)
    user = repo.create(
        telegram_id=101,
        username="ivan",
        full_name="Иванов Иван",
        role=UserRole.USER,
    )
    return user


def test_create_user(db_session):
    user = _make_user(db_session)
    db_session.flush()
    saved = db_session.get(User, user.id)
    assert saved is not None
    assert saved.telegram_id == 101
    assert saved.full_name == "Иванов Иван"
    assert saved.role == UserRole.USER


def test_get_user_by_telegram_id(db_session):
    _make_user(db_session)
    db_session.flush()
    repo = UserRepository(db_session)
    user = repo.get_by_telegram_id(101)
    assert user is not None
    assert user.username == "ivan"


def test_get_or_create_existing(db_session):
    _make_user(db_session)
    db_session.flush()
    repo = UserRepository(db_session)
    user = repo.get_or_create(telegram_id=101, full_name="Другое имя")
    db_session.flush()
    assert user.full_name == "Иванов Иван"
    assert db_session.query(User).count() == 1


def test_get_or_create_new(db_session):
    repo = UserRepository(db_session)
    user = repo.get_or_create(telegram_id=202, full_name="Петров Пётр")
    db_session.flush()
    assert user.id is not None
    assert repo.get_by_telegram_id(202) is not None


def test_create_request(db_session):
    user = _make_user(db_session)
    db_session.flush()
    repo = RequestRepository(db_session)
    request = repo.create(
        user=user,
        full_name="Иванов Иван",
        class_name="10А",
        reason="Не работает экран",
        photo_file_id="file_id_1",
    )
    db_session.flush()
    saved = db_session.get(Request, request.id)
    assert saved is not None
    assert saved.user_id == user.id
    assert saved.status == RequestStatus.NEW
    assert saved.photo_file_id == "file_id_1"


def test_get_request_returns_correct(db_session):
    user = _make_user(db_session)
    db_session.flush()
    repo = RequestRepository(db_session)
    request = repo.create(
        user=user,
        full_name="Иванов Иван",
        class_name="10А",
        reason="Причина",
        photo_file_id="f1",
    )
    db_session.flush()
    fetched = repo.get(request.id)
    assert fetched is not None
    assert fetched.id == request.id


def test_get_request_not_found_raises(db_session):
    repo = RequestRepository(db_session)
    with pytest.raises(RequestNotFoundError):
        repo.get_or_404(9999)


def test_get_user_requests_only_own(db_session):
    user1 = _make_user(db_session)
    repo_user = UserRepository(db_session)
    user2 = repo_user.create(
        telegram_id=102, username="petr", full_name="Петров Пётр"
    )
    db_session.flush()
    repo = RequestRepository(db_session)
    r1 = repo.create(user=user1, full_name="Иванов", class_name="10А",
                     reason="Р1", photo_file_id="f1")
    r2 = repo.create(user=user2, full_name="Петров", class_name="9Б",
                     reason="Р2", photo_file_id="f2")
    db_session.flush()
    results = repo.list_by_user(user1)
    ids = [r.id for r in results]
    assert r1.id in ids
    assert r2.id not in ids


def test_change_status(db_session):
    user = _make_user(db_session)
    db_session.flush()
    repo = RequestRepository(db_session)
    request = repo.create(
        user=user, full_name="Иванов", class_name="10А",
        reason="Р", photo_file_id="f1",
    )
    db_session.flush()
    updated = repo.update_status(request.id, RequestStatus.IN_PROGRESS)
    db_session.flush()
    assert updated.status == RequestStatus.IN_PROGRESS
    assert db_session.get(Request, request.id).status == RequestStatus.IN_PROGRESS


def test_reopen_request_after_init(db_session):
    user = _make_user(db_session)
    db_session.flush()
    repo = RequestRepository(db_session)
    request = repo.create(
        user=user, full_name="Иванов", class_name="10А",
        reason="Р", photo_file_id="f1",
    )
    db_session.flush()
    assert repo.get(request.id) is not None
    assert repo.get_or_404(request.id).id == request.id


def test_repository_error_on_create(db_session):
    pytest.importorskip("sqlalchemy")
    from database.repositories.requests import RequestRepository

    class BrokenSession:
        def add(self, obj):
            raise RuntimeError("boom")

        def flush(self):
            raise RuntimeError("boom")

        def rollback(self):
            pass

    repo = RequestRepository(BrokenSession())
    with pytest.raises(RequestRepositoryError):
        repo.create(
            user=None,
            full_name="Иванов",
            class_name="10А",
            reason="Р",
            photo_file_id="f1",
        )
