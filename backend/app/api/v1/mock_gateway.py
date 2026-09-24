"""MockGateway routes (Package B)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, request_id_dep, require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.payment import ChaosSetting, GatewayPayRequest, GatewayPayResponse
from app.services import gateway_service

router = APIRouter(prefix="/mock-gateway", tags=["mock-gateway"])


@router.get("/chaos", response_model=ChaosSetting)
async def get_chaos(
    request_id: str = Depends(request_id_dep),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> ChaosSetting:
    return ChaosSetting(**gateway_service.get_chaos())


@router.post("/chaos", response_model=ChaosSetting)
async def set_chaos(
    req: ChaosSetting,
    request_id: str = Depends(request_id_dep),
    user: User = Depends(require_role(Role.ADMIN.value)),
) -> ChaosSetting:
    try:
        return ChaosSetting(**gateway_service.set_chaos(req.mode, req.delay_seconds))
    except ValueError as e:
        raise HTTPException(422, detail={"error": {"code": "invalid_chaos_mode", "message": str(e)}})


@router.post("/pay", response_model=GatewayPayResponse, status_code=202)
async def gateway_pay(
    req: GatewayPayRequest,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
) -> GatewayPayResponse:
    """Internal: called by /payments/initiate to issue a gateway ref + schedule callback."""
    gref = gateway_service.new_gateway_ref()
    # Schedule the async callback (fire-and-forget).
    asyncio.create_task(
        gateway_service.schedule_callback(req.payment_id, gref, req.amount, chaos=req.chaos)
    )
    return GatewayPayResponse(
        gateway_ref=gref,
        redirect_url=f"/mock-gateway/redirect/{gref}",
        status="PENDING",
    )
