from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.dependencies import get_vm_service
from app.models.errors import ErrorResponse
from app.models.vm import (
    VMCreate,
    VMCreateAccepted,
    VMOperationResponse,
    VMRead,
    VMStatusResponse,
)
from app.services.vm_service import VMService

router = APIRouter(
    prefix="/vms",
    tags=["virtual-machines"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Virtual machine not found",
        },
    },
)

VMServiceDep = Annotated[VMService, Depends(get_vm_service)]


@router.post(
    "",
    response_model=VMCreateAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a virtual machine",
    responses={status.HTTP_202_ACCEPTED: {"description": "VM provisioning accepted"}},
)
async def create_vm(
    payload: VMCreate,
    background_tasks: BackgroundTasks,
    service: VMServiceDep,
) -> VMCreateAccepted:
    """Queue VM provisioning and return the task identifier immediately."""
    accepted = await service.create_vm(payload)
    background_tasks.add_task(service.provision_vm, accepted.task_id, accepted.vm_id, payload)
    return accepted


@router.get(
    "/{vm_id}",
    response_model=VMRead,
    summary="Get a virtual machine",
    responses={status.HTTP_200_OK: {"description": "Virtual machine details returned"}},
)
async def get_vm(vm_id: str, service: VMServiceDep) -> VMRead:
    """Return VM details for the supplied VM identifier, or a structured 404 error."""
    return await service.get_vm(vm_id)


@router.get(
    "/{vm_id}/status",
    response_model=VMStatusResponse,
    summary="Get VM provisioning status",
    responses={status.HTTP_200_OK: {"description": "VM state and latest task status returned"}},
)
async def get_vm_status(vm_id: str, service: VMServiceDep) -> VMStatusResponse:
    """Return current VM lifecycle state and the latest task associated with the VM."""
    return await service.get_vm_status(vm_id)


@router.delete(
    "/{vm_id}",
    response_model=VMOperationResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a virtual machine",
    responses={status.HTTP_200_OK: {"description": "Virtual machine deleted"}},
)
async def delete_vm(vm_id: str, service: VMServiceDep) -> VMOperationResponse:
    """Delete a VM inventory record by identifier, or return a structured 404 error."""
    vm = await service.delete_vm(vm_id)
    return VMOperationResponse(vm=vm, message="VM deleted")
