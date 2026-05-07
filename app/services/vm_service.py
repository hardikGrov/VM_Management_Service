import logging

from app.core.exceptions import VMConflictError, VMNotFoundError, VMProviderError
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

    def create_vm(self, payload: VMCreate) -> VMRead:
        logger.info(
            "Creating VM name=%s image=%s region=%s",
            payload.name,
            payload.image,
            payload.region,
        )
        try:
            vm = self._repository.create(payload)
        except VMRepositoryConflictError as exc:
            logger.warning("VM create rejected by provider: %s", exc)
            raise VMConflictError(str(exc)) from exc
        except VMRepositoryError as exc:
            logger.exception("VM create failed at provider")
            raise VMProviderError("Unable to create VM at this time.") from exc

        logger.info("Created VM id=%s name=%s", vm.id, vm.name)
        return vm

    def get_vm(self, vm_id: str) -> VMRead:
        logger.info("Fetching VM id=%s", vm_id)
        try:
            return self._repository.get(vm_id)
        except VMRepositoryNotFoundError as exc:
            logger.info("VM not found id=%s", vm_id)
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryError as exc:
            logger.exception("VM fetch failed at provider id=%s", vm_id)
            raise VMProviderError("Unable to fetch VM at this time.") from exc

    def delete_vm(self, vm_id: str) -> VMRead:
        logger.info("Deleting VM id=%s", vm_id)
        vm = self.get_vm(vm_id)
        try:
            self._repository.delete(vm_id)
        except VMRepositoryNotFoundError as exc:
            logger.info("VM disappeared before delete id=%s", vm_id)
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryConflictError as exc:
            logger.warning("VM delete rejected by provider id=%s: %s", vm_id, exc)
            raise VMConflictError(str(exc)) from exc
        except VMRepositoryError as exc:
            logger.exception("VM delete failed at provider id=%s", vm_id)
            raise VMProviderError("Unable to delete VM at this time.") from exc

        logger.info("Deleted VM id=%s", vm_id)
        return vm
