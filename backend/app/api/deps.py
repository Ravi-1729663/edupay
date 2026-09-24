"""FastAPI dependencies: request_id, current user, RBAC.

Authorization lives HERE, in the backend. Frontend hiding is UX, not security.
"""
from __future__ import annotations

from typing import Iterable, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger, new_request_id, request_id_ctx, user_id_ctx
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import Role, User

log = get_logger(__name__)


async def request_id_dep(
    request: Request,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> str:
    rid = x_request_id or new_request_id()
    request_id_ctx.set(rid)
    return rid


class CurrentUser:
    """Resolve the Bearer token to a User row; attach user_id to log context."""

    def __init__(self, *, allow_inactive: bool = False):
        self.allow_inactive = allow_inactive

    async def __call__(self, request: Request, x_request_id: str = Depends(request_id_dep), db: Session = Depends(get_db)) -> User:
        auth: Optional[str] = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "unauthenticated", "message": "missing bearer token"}},
            )
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "invalid_token", "message": "token invalid or expired"}},
            )
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id:
            raise HTTPException(status_code=401, detail={"error": {"code": "invalid_token", "message": "no sub"}})
        user = db.get(User, user_id)
        if not user or (not user.is_active and not self.allow_inactive):
            raise HTTPException(status_code=401, detail={"error": {"code": "invalid_token", "message": "user not found / inactive"}})
        if user.role.value != role:
            # role changed since token issue — fail closed
            raise HTTPException(status_code=403, detail={"error": {"code": "role_mismatch", "message": "token role differs from current"}})
        user_id_ctx.set(user.id)
        return user


get_current_user = CurrentUser()


def require_role(*roles: str):
    """RBAC dependency factory. Returns a dependency that 403s on mismatch."""
    allowed = set(roles)

    async def _dep(
        user: User = Depends(get_current_user),
        x_request_id: str = Depends(request_id_dep),
    ) -> User:
        if user.role.value not in allowed:
            log.info(
                "rbac.deny",
                extra={
                    "user_id": user.id,
                    "role": user.role.value,
                    "required": sorted(allowed),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "forbidden",
                        "message": f"role {user.role.value} not allowed; requires one of {sorted(allowed)}",
                    }
                },
            )
        return user

    return _dep


def require_active_student_self_or_staff():
    """STUDENT may only see their own data; staff/manager/admin see all.
    Used by per-student routes."""
    async def _dep(student_id: str, user: User = Depends(get_current_user)) -> User:
        if user.role == Role.STUDENT and user.student_id != student_id:
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "forbidden", "message": "students can only see their own data"}},
            )
        if user.role == Role.STUDENT and not user.is_active:
            raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "inactive"}})
        return user
    return _dep
