"""Auth routes: login + me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, request_id_dep
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.auth_service import InvalidCredentials, login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login_route(
    req: LoginRequest,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        return login(db, req, request_id)
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_credentials", "message": "email or password incorrect"}},
        )


@router.get("/me", response_model=UserRead)
async def me(
    request_id: str = Depends(request_id_dep),
    user: User = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(user)
