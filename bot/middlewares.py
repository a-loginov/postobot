from services.request_service import RequestService
from database.database import SessionLocal
from database.repositories.requests import RequestRepository
from database.repositories.users import UserRepository


def get_request_service():
    session = SessionLocal()
    try:
        user_repo = UserRepository(session)
        request_repo = RequestRepository(session)
        return RequestService(request_repo, user_repo), session
    except Exception:
        session.close()
        raise
