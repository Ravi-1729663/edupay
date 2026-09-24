"""Common schemas: pagination, error envelope, money helpers."""
from __future__ import annotations

from decimal import Decimal
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


T = TypeVar("T")


class Page(ORMBase, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str


def money(v: Decimal | None) -> str:
    """Serialise money as a 2-dp string to avoid float precision loss in JSON."""
    if v is None:
        return None
    return f"{Decimal(v):.2f}"
