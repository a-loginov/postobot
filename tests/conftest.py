import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import database
from database.database import get_session, init_db
from database.models import Base
from database.repositories.requests import RequestRepository
from database.repositories.users import UserRepository
from services.request_service import RequestService


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    old_engine = database.engine
    old_session = database.SessionLocal
    database.engine = engine
    database.SessionLocal = TestSession

    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        database.engine = old_engine
        database.SessionLocal = old_session


@pytest.fixture()
def user_repo(db_session):
    return UserRepository(db_session)


@pytest.fixture()
def request_repo(db_session):
    return RequestRepository(db_session)


@pytest.fixture()
def request_service(db_session):
    return RequestService(RequestRepository(db_session), UserRepository(db_session))
