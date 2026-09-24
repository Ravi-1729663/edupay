"""User CRUD service (admin only)."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.security import hash_password
from app.models.user import Role, User
from app.schemas.auth import UserCreate, UserRead, UserUpdate

from app.core.logging import get_logger

log = get_logger(__name__)


class EmailExists(Exception):
    pass


class NotFound(Exception):
    pass


def _to_read(u: User) -> UserRead:
    return UserRead.model_validate(u)


def list_users(
    db: Session,
    *,
    role: Optional[Role] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[User], int]:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
        count_stmt = count_stmt.where(User.is_active == is_active)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.email.ilike(like)) | (User.full_name.ilike(like)))
        count_stmt = count_stmt.where(
            (User.email.ilike(like)) | (User.full_name.ilike(like))
        )
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, int(total)


def get_user(db: Session, user_id: str) -> User:
    u = db.get(User, user_id)
    if not u:
        raise NotFound()
    return u


def create_user(db: Session, req: UserCreate, actor_id: str) -> User:
    u = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        student_id=req.student_id,
        is_active=True,
        created_by=actor_id,
    )
    db.add(u)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise EmailExists() from e
    write_audit(
        db,
        actor_user_id=actor_id,
        action="user.create",
        entity_type="user",
        entity_id=u.id,
        metadata={"email": u.email, "role": u.role.value},
    )
    db.commit()
    db.refresh(u)
    return u


def update_user(db: Session, user_id: str, req: UserUpdate, actor_id: str) -> User:
    u = get_user(db, user_id)
    changed = []
    if req.full_name is not None:
        u.full_name = req.full_name
        changed.append("full_name")
    if req.role is not None:
        u.role = req.role
        changed.append("role")
    if req.is_active is not None:
        u.is_active = req.is_active
        changed.append("is_active")
    if req.student_id is not None:
        u.student_id = req.student_id
        changed.append("student_id")
    write_audit(
        db,
        actor_user_id=actor_id,
        action="user.update",
        entity_type="user",
        entity_id=u.id,
        metadata={"fields": changed},
    )
    db.commit()
    db.refresh(u)
    return u


def deactivate_user(db: Session, user_id: str, actor_id: str) -> User:
    u = get_user(db, user_id)
    u.is_active = False
    write_audit(
        db,
        actor_user_id=actor_id,
        action="user.deactivate",
        entity_type="user",
        entity_id=u.id,
        metadata={},
    )
    db.commit()
    db.refresh(u)
    return u
