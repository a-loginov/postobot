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
from database.models import Request as DBRequest
from database.models import RequestStatus, User

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
            return RedirectResponse(url="/admin/dashboard", status_code=303)
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
        resp = RedirectResponse(url="/admin/dashboard", status_code=303)
        resp.set_cookie(
            AUTH_COOKIE,
            token,
            max_age=AUTH_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=False,
        )
        return resp

    @app.get("/admin/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request, db: Session = Depends(get_session)):
        if not is_authed(request):
            return redirect_login()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        total_requests = db.query(func.count(DBRequest.id)).scalar() or 0
        today_requests = (
            db.query(func.count(DBRequest.id))
            .filter(DBRequest.created_at >= today_start)
            .scalar()
            or 0
        )
        week_requests = (
            db.query(func.count(DBRequest.id))
            .filter(DBRequest.created_at >= week_start)
            .scalar()
            or 0
        )
        total_users = db.query(func.count(User.id)).scalar() or 0

        status_counts = {
            k.value: v
            for k, v in db.query(DBRequest.status, func.count(DBRequest.id))
            .group_by(DBRequest.status)
            .all()
        }

        recent_requests = (
            db.query(DBRequest)
            .options(selectinload(DBRequest.user))
            .order_by(DBRequest.created_at.desc())
            .limit(10)
            .all()
        )

        # Requests per day for the last 7 days
        days_spans = []
        for i in range(6, -1, -1):
            day = today_start - timedelta(days=i)
            day_end = day + timedelta(days=1)
            count = (
                db.query(func.count(DBRequest.id))
                .filter(DBRequest.created_at >= day, DBRequest.created_at < day_end)
                .scalar()
                or 0
            )
            days_spans.append(
                {"label": day.strftime("%d.%m"), "count": count}
            )

        max_day_count = max((d["count"] for d in days_spans), default=1) or 1

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "title": "Дашборд",
                "active": "dashboard",
                "total_requests": total_requests,
                "today_requests": today_requests,
                "week_requests": week_requests,
                "total_users": total_users,
                "status_counts": status_counts,
                "status_labels": STATUS_LABELS,
                "recent_requests": recent_requests,
                "days_spans": days_spans,
                "max_day_count": max_day_count,
            },
        )

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
