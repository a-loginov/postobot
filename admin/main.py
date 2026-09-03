import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

import config
from database.database import SessionLocal
from database.models import Feedback, Request as DBRequest, RequestStatus, User, UserRole

logger = logging.getLogger(__name__)

AUTH_COOKIE = "postobot_admin"
AUTH_MAX_AGE = 60 * 60 * 12  # 12 hours

STATUS_LABELS = {
    "NEW": "Новые",
    "IN_PROGRESS": "В работе",
    "COMPLETED": "Выполнено",
    "REJECTED": "Отклонено",
}

STATUS_TRANSITIONS = {
    RequestStatus.NEW: [RequestStatus.IN_PROGRESS, RequestStatus.REJECTED],
    RequestStatus.IN_PROGRESS: [RequestStatus.COMPLETED, RequestStatus.REJECTED],
    RequestStatus.COMPLETED: [],
    RequestStatus.REJECTED: [],
}


def create_app() -> FastAPI:
    templates = Jinja2Templates(directory=str(config.BASE_DIR / "admin" / "templates"))
    serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="postobot-admin")

    app = FastAPI(title="ПостоБот — Админ-панель", docs_url=None, redoc_url=None)

    def make_token() -> str:
        return serializer.dumps({"role": "admin"})

    def verify_token(token: str) -> bool:
        try:
            data = serializer.loads(token, max_age=AUTH_MAX_AGE)
            return data.get("role") == "admin"
        except BadSignature:
            return False

    def get_session() -> Session:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def is_authed(request: Request) -> bool:
        token = request.cookies.get(AUTH_COOKIE)
        return bool(token and verify_token(token))

    def redirect_login() -> RedirectResponse:
        return RedirectResponse(url="/admin", status_code=303)

    def _status_label(status: RequestStatus) -> str:
        return STATUS_LABELS.get(status.value, status.value)

    @app.get("/")
    async def root():
        return RedirectResponse(url="/admin", status_code=303)

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_home(request: Request):
        if is_authed(request):
            return RedirectResponse(url="/admin/requests", status_code=303)
        return templates.TemplateResponse(
            request, "login.html", {"error": None, "title": "Вход в админ-панель"}
        )

    @app.post("/admin/login", response_class=HTMLResponse)
    async def admin_login(
        request: Request,
        password: str = Form(""),
    ):
        if password != config.ADMIN_PASSWORD:
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "error": "Неверный пароль",
                    "title": "Вход в админ-панель",
                },
                status_code=401,
            )
        token = make_token()
        resp = RedirectResponse(url="/admin/requests", status_code=303)
        resp.set_cookie(
            AUTH_COOKIE,
            token,
            max_age=AUTH_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=False,
        )
        return resp

    @app.get("/admin/requests", response_class=HTMLResponse)
    async def requests_list(
        request: Request,
        status: str = "ALL",
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        query = db.query(DBRequest).options(selectinload(DBRequest.user))
        if status in STATUS_LABELS:
            query = query.filter(DBRequest.status == RequestStatus(status))
        requests = query.order_by(DBRequest.created_at.desc()).all()

        return templates.TemplateResponse(
            request,
            "requests.html",
            {
                "title": "Заявки",
                "active": "requests",
                "requests": requests,
                "current_status": status,
                "status_labels": STATUS_LABELS,
                "status_label": lambda s: _status_label(s),
            },
        )

    @app.get("/admin/requests/{request_id}", response_class=HTMLResponse)
    async def request_detail(
        request: Request,
        request_id: int,
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        req = (
            db.query(DBRequest)
            .options(selectinload(DBRequest.user))
            .filter(DBRequest.id == request_id)
            .first()
        )
        if req is None:
            return templates.TemplateResponse(
                request,
                "request_detail.html",
                {"title": "Заявка не найдена", "active": "requests", "req": None},
                status_code=404,
            )

        return templates.TemplateResponse(
            request,
            "request_detail.html",
            {
                "title": f"Заявка №{req.id}",
                "active": "requests",
                "req": req,
                "status_label": lambda s: _status_label(s),
                "transitions": STATUS_TRANSITIONS.get(req.status, []),
            },
        )

    @app.post("/admin/requests/{request_id}/status")
    async def update_status(
        request: Request,
        request_id: int,
        new_status: str = Form(""),
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        try:
            target = RequestStatus(new_status)
        except ValueError:
            return RedirectResponse(
                url=f"/admin/requests/{request_id}", status_code=303
            )

        req = db.query(DBRequest).filter(DBRequest.id == request_id).first()
        if req is not None:
            allowed = STATUS_TRANSITIONS.get(req.status, [])
            if target in allowed or target == req.status:
                req.status = target
                db.commit()

        return RedirectResponse(
            url=f"/admin/requests/{request_id}", status_code=303
        )

    @app.get("/admin/feedback", response_class=HTMLResponse)
    async def feedback_list(
        request: Request,
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        feedbacks = (
            db.query(Feedback)
            .order_by(Feedback.created_at.desc())
            .all()
        )

        return templates.TemplateResponse(
            request,
            "feedback.html",
            {
                "title": "Обратная связь",
                "active": "feedback",
                "feedbacks": feedbacks,
            },
        )

    @app.get("/admin/access", response_class=HTMLResponse)
    async def access_list(
        request: Request,
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        users = db.query(User).order_by(User.created_at.desc()).all()

        return templates.TemplateResponse(
            request,
            "access.html",
            {
                "title": "Управление доступом",
                "active": "access",
                "users": users,
                "role_labels": {"USER": "Пользователь", "ADMIN": "Администратор"},
            },
        )

    @app.post("/admin/access/{user_id}/role")
    async def update_user_role(
        request: Request,
        user_id: int,
        new_role: str = Form(""),
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        try:
            target = UserRole(new_role)
        except ValueError:
            return RedirectResponse(url="/admin/access", status_code=303)

        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            user.role = target
            db.commit()

        return RedirectResponse(url="/admin/access", status_code=303)

    @app.post("/admin/access/add")
    async def add_admin(
        request: Request,
        telegram_id: int = Form(...),
        db: Session = Depends(get_session),
    ):
        if not is_authed(request):
            return redirect_login()

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user is None:
            user = User(telegram_id=telegram_id, role=UserRole.ADMIN)
            db.add(user)
        else:
            user.role = UserRole.ADMIN
        db.commit()

        return RedirectResponse(url="/admin/access", status_code=303)

    @app.get("/admin/logout")
    async def logout():
        resp = RedirectResponse(url="/admin", status_code=303)
        resp.delete_cookie(AUTH_COOKIE)
        return resp

    return app


def run_server() -> None:
    """Start the admin panel with uvicorn in a background thread."""
    import uvicorn

    app = create_app()
    uvicorn.run(
        app,
        host=config.ADMIN_HOST,
        port=config.ADMIN_PORT,
        log_level="warning",
    )
    logger.info("Админ-панель остановлена")


def start_admin_server() -> threading.Thread:
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
