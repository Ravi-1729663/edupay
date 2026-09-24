"""Auth service: login + token minting."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.core.logging import get_logger, user_id_ctx
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead

log = get_logger(__name__)


class InvalidCredentials(Exception):
    pass


def login(db: Session, req: LoginRequest, request_id: str) -> TokenResponse:
    user = db.execute(
        select(User).where(User.email == req.email)
    ).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        log.info("auth.login.failed", extra={"email": req.email})
        raise InvalidCredentials()
    token = create_access_token(user.id, user.email, user.role.value)
    write_audit(
        db,
        actor_user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        metadata={"request_id": request_id},
    )
    db.commit()
    user_id_ctx.set(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )
