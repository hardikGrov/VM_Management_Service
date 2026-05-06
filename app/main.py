from fastapi import FastAPI

from app.api.routes.vms import router as vm_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "API for managing virtual machine lifecycle operations including "
        "provisioning, start, stop, reboot, and deletion."
    ),
    version="0.1.0",
    contact={"name": "Platform Engineering"},
    openapi_tags=[
        {
            "name": "health",
            "description": "Service health and readiness endpoints.",
        },
        {
            "name": "virtual-machines",
            "description": "Create, inspect, and manage virtual machine lifecycle state.",
        },
    ],
)

register_error_handlers(app)


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description="Returns service health for load balancers and uptime probes.",
)
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


app.include_router(vm_router, prefix="/v1")
