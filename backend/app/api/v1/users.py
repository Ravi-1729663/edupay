"""User CRUD routes — admin only."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_role, request_id_dep
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.schemas.common import Page
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
@router.get("/", response_model=Page[UserRead], include_in_schema=False)
async def list_users(
    role: Optional[Role] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> Page[UserRead]:
    items, total = user_service.list_users(
        db, role=role, is_active=is_active, q=q, limit=limit, offset=offset
    )
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=UserRead, status_code=201)
@router.post("/", response_model=UserRead, status_code=201, include_in_schema=False)
async def create_user(
    req: UserCreate,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> UserRead:
    try:
        return UserRead.model_validate(user_service.create_user(db, req, user.id))
    except user_service.EmailExists:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "email_exists", "message": "a user with this email already exists"}},
        )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> UserRead:
    try:
        return UserRead.model_validate(user_service.get_user(db, user_id))
    except user_service.NotFound:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "user not found"}})


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    req: UserUpdate,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> UserRead:
    try:
        return UserRead.model_validate(user_service.update_user(db, user_id, req, user.id))
    except user_service.NotFound:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "user not found"}})


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> UserRead:
    try:
        return UserRead.model_validate(user_service.deactivate_user(db, user_id, user.id))
    except user_service.NotFound:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "user not found"}})
