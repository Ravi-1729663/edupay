"""MockGateway + Chaos mode (Package B).

The MockGateway is part of the same modular-monolith app. It:
  - issues a gateway_ref on /mock-gateway/pay
  - schedules an async callback to /payments/webhook per the current chaos mode

Chaos storage: an in-memory singleton (dev-only; lost on restart, which is
fine for the chaos panel). The setting forces the *next* payment's outcome:
  SUCCESS | FAILED | TIMEOUT_NO_CALLBACK | DUPLICATE_CALLBACK | LATE_CALLBACK
"""
from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

VALID_MODES = {
    "SUCCESS",
    "FAILED",
    "TIMEOUT_NO_CALLBACK",
    "DUPLICATE_CALLBACK",
    "LATE_CALLBACK",
}


@dataclass
class _ChaosStore:
    mode: str = "SUCCESS"
    delay_seconds: int = 0


# Module-level singleton. Tests can reset via `reset_chaos()`.
_store: _ChaosStore = _ChaosStore()

# True outcome per gateway_ref, set when the callback is scheduled. The verify
# endpoint reads this to resolve UNKNOWN payments. In-memory (dev-only).
_outcomes: dict[str, str] = {}


def get_chaos() -> dict:
    return {"mode": _store.mode, "delay_seconds": _store.delay_seconds}


def set_chaos(mode: str, delay_seconds: int = 0) -> dict:
    if mode not in VALID_MODES:
        raise ValueError(f"invalid chaos mode {mode}; expected one of {sorted(VALID_MODES)}")
    _store.mode = mode
    _store.delay_seconds = max(0, int(delay_seconds))
    log.info("chaos.set", extra={"mode": _store.mode, "delay_seconds": _store.delay_seconds})
    return get_chaos()


def reset_chaos() -> None:
    """Test helper."""
    _store.mode = "SUCCESS"
    _store.delay_seconds = 0
    _outcomes.clear()


def record_true_outcome(gateway_ref: str, status: str) -> None:
    _outcomes[gateway_ref] = status


def get_true_outcome(gateway_ref: str) -> str:
    """Returns the gateway's true outcome for a ref, or UNKNOWN if unknown."""
    return _outcomes.get(gateway_ref, "UNKNOWN")


def new_gateway_ref() -> str:
    return "GW-" + uuid.uuid4().hex[:16].upper()


def _callback_url() -> str:
    # The gateway calls itself (same process). In docker, the backend service
    # is reachable at http://backend:8000; locally at http://localhost:8000.
    # We always use localhost because the gateway runs in-process.
    return "http://localhost:8000/payments/webhook"


async def schedule_callback(payment_id: str, gateway_ref: str, amount, chaos: Optional[str] = None) -> None:
    """Fire the async gateway callback per the chaos mode.

    Called as a fire-and-forget asyncio task from /mock-gateway/pay.
    Also records the gateway's *true* outcome so verify() can resolve UNKNOWN.
    """
    mode = chaos or _store.mode
    delay = _store.delay_seconds
    url = _callback_url()
    payload = {
        "gateway_ref": gateway_ref,
        "amount": str(amount),
    }

    # Record the true outcome regardless of whether the callback fires.
    if mode == "FAILED":
        record_true_outcome(gateway_ref, "FAILED")
    else:
        # SUCCESS, TIMEOUT_NO_CALLBACK, DUPLICATE_CALLBACK, LATE_CALLBACK
        # all mean the payment actually succeeded at the gateway.
        record_true_outcome(gateway_ref, "SUCCESS")

    async def _fire(status: str) -> None:
        body = {**payload, "status": status, "paid_at": None}
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(url, json=body)
                log.info("chaos.callback", extra={"gateway_ref": gateway_ref, "status": status, "http": r.status_code})
        except Exception as e:  # noqa: BLE001
            log.warning("chaos.callback.error", extra={"gateway_ref": gateway_ref, "err": str(e)})

    if mode == "SUCCESS":
        await _fire("SUCCESS")
    elif mode == "FAILED":
        await _fire("FAILED")
    elif mode == "TIMEOUT_NO_CALLBACK":
        log.info("chaos.no_callback", extra={"gateway_ref": gateway_ref, "payment_id": payment_id})
        # Intentionally do nothing → payment stays PENDING → becomes UNKNOWN via verify.
    elif mode == "DUPLICATE_CALLBACK":
        # Fire twice rapidly. The webhook's SELECT...FOR UPDATE + status check
        # ensures exactly one financial record is created.
        await _fire("SUCCESS")
        await _fire("SUCCESS")
    elif mode == "LATE_CALLBACK":
        await asyncio.sleep(delay)
        await _fire("SUCCESS")
    else:  # defensive
        await _fire("SUCCESS")
