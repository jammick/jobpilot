import secrets
from typing import Annotated
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import decode_token
from app.models import User

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]

def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: DB) -> User:
    # Docker's local workspace deliberately has no login screen. Browsers may
    # retain a token from an earlier build, so resolve the local workspace
    # before looking at an optional Authorization header.
    if get_settings().local_workspace_mode:
        user = db.query(User).filter_by(email="local@jobpilot.workspace").first()
        if not user:
            user = User(email="local@jobpilot.workspace", password_hash="local-workspace-no-login")
            db.add(user); db.commit(); db.refresh(user)
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
