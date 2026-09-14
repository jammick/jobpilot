import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Depends, Header, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import create_workspace_token, decode_token, decode_workspace_token
from app.models import User

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]

LOCAL_WORKSPACE_EMAIL = "local@jobpilot.workspace"
KNOWLEDGE_OWNER_EMAIL = "knowledge@jobpilot.system"


def _get_or_create_user(db: Session, email: str, *, anonymous: bool = False) -> User:
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            password_hash="managed-workspace-no-login",
            is_anonymous=anonymous,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def knowledge_owner(db: Session) -> User:
    """Return the developer-owned account behind the global knowledge base."""
    settings = get_settings()
    email = LOCAL_WORKSPACE_EMAIL if settings.local_workspace_mode else KNOWLEDGE_OWNER_EMAIL
    return _get_or_create_user(db, email)


def current_user(
    request: Request,
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DB,
) -> User:
    # Docker's local workspace deliberately has no login screen. Browsers may
    # retain a token from an earlier build, so resolve the local workspace
    # before looking at an optional Authorization header.
    if get_settings().local_workspace_mode:
        return _get_or_create_user(db, LOCAL_WORKSPACE_EMAIL)
    settings = get_settings()
    if settings.anonymous_workspace_mode:
        token = request.cookies.get(settings.workspace_cookie_name)
        user_id = decode_workspace_token(token) if token else None
        user = db.get(User, user_id) if user_id else None
        now = datetime.now(timezone.utc)
        expires_at = user.expires_at if user else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not user or not user.is_anonymous or (expires_at and expires_at < now):
            # Opportunistic cleanup keeps abandoned public demo workspaces from
            # growing forever without requiring a paid scheduler.
            db.query(User).filter(User.is_anonymous.is_(True), User.expires_at < now).delete(
                synchronize_session=False
            )
            user = User(
                email=f"anon+{uuid.uuid4()}@jobpilot.workspace",
                password_hash="anonymous-workspace-no-login",
                is_anonymous=True,
                expires_at=now + timedelta(days=settings.workspace_ttl_days),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            response.set_cookie(
                settings.workspace_cookie_name,
                create_workspace_token(user.id),
                max_age=settings.workspace_ttl_days * 86400,
                httponly=True,
                secure=settings.workspace_cookie_secure,
                samesite="lax",
                path="/",
            )
        return user
    if credentials:
        user = db.get(User, decode_token(credentials.credentials))
        if not user: raise HTTPException(status_code=401, detail="用户不存在")
        return user
    raise HTTPException(status_code=401, detail="请先登录")

CurrentUser = Annotated[User, Depends(current_user)]


def require_knowledge_admin(x_knowledge_admin_key: Annotated[str | None, Header()] = None) -> None:
    configured = get_settings().knowledge_admin_key
    if not configured or not x_knowledge_admin_key or not secrets.compare_digest(configured, x_knowledge_admin_key):
        raise HTTPException(403, detail="知识库管理仅对开发者开放")


KnowledgeAdmin = Annotated[None, Depends(require_knowledge_admin)]
