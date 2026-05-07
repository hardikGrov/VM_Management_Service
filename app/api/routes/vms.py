from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_vm_service
from app.models.errors import ErrorResponse
from app.models.vm import (
    VMCreate,
    VMOperationResponse,
    VMRead,
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
    response_model=VMRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a virtual machine",
    responses={status.HTTP_201_CREATED: {"description": "Virtual machine created"}},
)
async def create_vm(payload: VMCreate, service: VMServiceDep) -> VMRead:
    """Create a VM inventory record with validated compute, image, and region settings."""
    return await service.create_vm(payload)


@router.get(
    "/{vm_id}",
    response_model=VMRead,
    summary="Get a virtual machine",
    responses={status.HTTP_200_OK: {"description": "Virtual machine details returned"}},
)
async def get_vm(vm_id: str, service: VMServiceDep) -> VMRead:
    """Return VM details for the supplied VM identifier, or a structured 404 error."""
    return await service.get_vm(vm_id)


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
