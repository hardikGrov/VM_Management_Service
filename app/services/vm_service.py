import logging

from app.core.exceptions import AppError, VMConflictError, VMNotFoundError, VMOperationError
from app.models.vm import VMCreate, VMRead
from app.repositories.vm_repository import (
    VMRepository,
    VMRepositoryConflictError,
    VMRepositoryError,
    VMRepositoryNotFoundError,
)

logger = logging.getLogger(__name__)


class VMService:
    def __init__(self, repository: VMRepository) -> None:
        self._repository = repository

    async def create_vm(self, payload: VMCreate) -> VMRead:
        logger.info(
            "Creating VM name=%s image=%s region=%s",
            payload.name,
            payload.image,
            payload.region,
        )
        try:
            vm = await self._repository.create_vm(payload)
        except AppError:
            raise
        except VMRepositoryConflictError as exc:
            logger.warning("VM create rejected by provider: %s", exc)
            raise VMConflictError(str(exc)) from exc
        except VMRepositoryError as exc:
            logger.exception("VM create failed at provider")
            raise VMOperationError("Unable to create VM at this time.") from exc

        logger.info("Created VM id=%s name=%s", vm.id, vm.name)
        return vm

    async def get_vm(self, vm_id: str) -> VMRead:
        logger.info("Fetching VM id=%s", vm_id)
        try:
            return await self._repository.get_vm(vm_id)
        except AppError:
            raise
        except VMRepositoryNotFoundError as exc:
            logger.info("VM not found id=%s", vm_id)
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryError as exc:
            logger.exception("VM fetch failed at provider id=%s", vm_id)
            raise VMOperationError("Unable to fetch VM at this time.") from exc

    async def list_vms(self) -> list[VMRead]:
        logger.info("Listing VMs")
        try:
            return list(await self._repository.list_vms())
        except AppError:
            raise
        except VMRepositoryError as exc:
            logger.exception("VM list failed at provider")
            raise VMOperationError("Unable to list VMs at this time.") from exc

    async def delete_vm(self, vm_id: str) -> VMRead:
        logger.info("Deleting VM id=%s", vm_id)
        vm = await self.get_vm(vm_id)
        try:
            await self._repository.delete_vm(vm_id)
        except AppError:
            raise
        except VMRepositoryNotFoundError as exc:
            logger.info("VM disappeared before delete id=%s", vm_id)
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryConflictError as exc:
            logger.warning("VM delete rejected by provider id=%s: %s", vm_id, exc)
            raise VMConflictError(str(exc)) from exc
        except VMRepositoryError as exc:
            logger.exception("VM delete failed at provider id=%s", vm_id)
            raise VMOperationError("Unable to delete VM at this time.") from exc

        logger.info("Deleted VM id=%s", vm_id)
        return vm

    async def start_vm(self, vm_id: str) -> VMRead:
        logger.info("Starting VM id=%s", vm_id)
        try:
            return await self._repository.start_vm(vm_id)
        except AppError:
            raise
        except VMRepositoryNotFoundError as exc:
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryError as exc:
            logger.exception("VM start failed at provider id=%s", vm_id)
            raise VMOperationError("Unable to start VM at this time.") from exc

    async def stop_vm(self, vm_id: str) -> VMRead:
        logger.info("Stopping VM id=%s", vm_id)
        try:
            return await self._repository.stop_vm(vm_id)
        except AppError:
            raise
        except VMRepositoryNotFoundError as exc:
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryError as exc:
            logger.exception("VM stop failed at provider id=%s", vm_id)
            raise VMOperationError("Unable to stop VM at this time.") from exc
