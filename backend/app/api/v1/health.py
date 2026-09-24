"""Health + readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import request_id_dep
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", include_in_schema=False)
async def health(response: Response, request_id: str = Depends(request_id_dep)) -> dict:
    response.status_code = status.HTTP_200_OK
    return {"status": "ok", "request_id": request_id}


@router.get("/ready", include_in_schema=False)
async def ready(
    response: Response,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
) -> dict:
    try:
        db.execute(text("SELECT 1"))
        response.status_code = status.HTTP_200_OK
        return {"status": "ready", "db": "ok", "request_id": request_id}
    except Exception as e:  # noqa: BLE001
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "db": "down", "error": str(e), "request_id": request_id}
