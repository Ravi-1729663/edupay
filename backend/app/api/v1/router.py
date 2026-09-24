"""v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.health import router as health_router
from app.api.v1.mock_gateway import router as mock_gateway_router
from app.api.v1.payments import router as payments_router
from app.api.v1.students import router as students_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(catalog_router)
api_router.include_router(students_router)
api_router.include_router(payments_router)
api_router.include_router(mock_gateway_router)
api_router.include_router(admin_router)
