from contextlib import contextmanager

from database.database import SessionLocal
from database.repositories.requests import RequestRepository
from database.repositories.users import UserRepository
from services.request_service import RequestService


@contextmanager
def unit_of_work():
    """Provide a RequestService + auto-closing session per handler call."""
    session = SessionLocal()
    try:
        user_repo = UserRepository(session)
        request_repo = RequestRepository(session)
        service = RequestService(request_repo, user_repo)
        yield service, session
        session.commit()
    finally:
        session.close()
