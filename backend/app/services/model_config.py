"""Per-user LLM configuration for the private JobPilot workspace.

Embedding settings remain deployment-owned in ``.env``.  This module only
handles the chat model used for JD parsing, advice, and resume optimisation.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import UserModelConfig


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None
    base_url: str | None
    chat_model: str


def masked_api_key(api_key: str | None) -> str | None:
    """Return a confirmation hint without exposing a reusable credential."""
    if not api_key:
        return None
    tail = api_key[-4:] if len(api_key) >= 4 else "••••"
    return f"••••••••{tail}"


def _cipher() -> Fernet:
    # The encryption root stays outside the database in JWT_SECRET. Production
    # deployments should provide a dedicated, high-entropy JWT secret.
    material = hashlib.sha256(
        ("jobpilot:model-config:" + get_settings().jwt_secret).encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def system_llm_config() -> LLMConfig:
    settings = get_settings()
    return LLMConfig(settings.openai_api_key, settings.openai_base_url, settings.chat_model)


def user_llm_config(db: Session, user_id: str) -> LLMConfig:
    row = db.get(UserModelConfig, user_id)
    if not row:
        return system_llm_config()
    fallback = system_llm_config()
    try:
        api_key = _cipher().decrypt(row.encrypted_api_key.encode("utf-8")).decode("utf-8") if row.encrypted_api_key else None
    except (InvalidToken, ValueError):
        # A rotated server secret deliberately invalidates old encrypted keys.
        api_key = None
    # A user may change only the provider/model and intentionally leave the
    # key field blank. In that case retain the deployment fallback key.
    return LLMConfig(api_key or fallback.api_key, row.base_url, row.chat_model)


def save_user_llm_config(
    db: Session,
    user_id: str,
    *,
    api_key: str | None,
    base_url: str | None,
    chat_model: str,
) -> LLMConfig:
    row = db.get(UserModelConfig, user_id)
    if not row:
        row = UserModelConfig(user_id=user_id, chat_model=chat_model)
        db.add(row)
    if api_key:
        row.encrypted_api_key = _cipher().encrypt(api_key.encode("utf-8")).decode("utf-8")
    row.base_url = base_url
    row.chat_model = chat_model
    db.commit()
    return user_llm_config(db, user_id)
