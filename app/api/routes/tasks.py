from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_vm_service
from app.models.errors import ErrorResponse
from app.models.vm import TaskRead
from app.services.vm_service import VMService

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Task not found",
        },
    },
)

VMServiceDep = Annotated[VMService, Depends(get_vm_service)]


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Get task details",
    responses={status.HTTP_200_OK: {"description": "Task details returned"}},
)
async def get_task(task_id: str, service: VMServiceDep) -> TaskRead:
    """Return task status, VM id, timestamps, and any provisioning error."""
    return await service.get_task(task_id)
