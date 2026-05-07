import logging

from app.core.exceptions import AppError, VMInvalidStateError, VMNotFoundError, VMOperationError
from app.models.vm import (
    TaskRead,
    TaskStatus,
    VMCreate,
    VMCreateAccepted,
    VMRead,
    VMState,
    VMStatusResponse,
)
from app.repositories.task_repository import TaskRepository
from app.repositories.vm_repository import (
    VMRepository,
    VMRepositoryError,
    VMRepositoryNotFoundError,
)

logger = logging.getLogger(__name__)


class VMService:
    _ALLOWED_TRANSITIONS = {
        VMState.PENDING: {VMState.PROVISIONING},
        VMState.PROVISIONING: {VMState.ACTIVE, VMState.ERROR},
        VMState.ACTIVE: {VMState.STOPPING, VMState.DELETING},
        VMState.STOPPING: {VMState.STOPPED, VMState.ERROR},
        VMState.DELETING: {VMState.DELETED, VMState.ERROR},
        VMState.ERROR: set(),
        VMState.STOPPED: set(),
        VMState.DELETED: set(),
    }

    def __init__(self, repository: VMRepository, task_repository: TaskRepository) -> None:
        self._repository = repository
        self._task_repository = task_repository

    async def create_vm(self, payload: VMCreate) -> VMCreateAccepted:
        logger.info(
            "Queueing VM provisioning name=%s image=%s region=%s",
            payload.name,
            payload.image,
            payload.region,
        )
        try:
            vm = await self._repository.reserve_vm(payload)
            task = await self._task_repository.create_task(
                vm_id=vm.id,
                status=TaskStatus.PROVISIONING,
            )
        except AppError:
            raise
        except VMRepositoryError as exc:
            logger.exception("Failed to reserve VM before provisioning")
            raise VMOperationError("Unable to queue VM provisioning.") from exc

        return VMCreateAccepted(task_id=task.task_id, vm_id=vm.id, status=task.status)

    async def provision_vm(self, task_id: str, vm_id: str, payload: VMCreate) -> None:
        logger.info("Starting VM provisioning task_id=%s vm_id=%s", task_id, vm_id)
        try:
            await self._transition_vm(vm_id, VMState.PROVISIONING)
            await self._repository.provision_vm(vm_id=vm_id, payload=payload)
            await self._transition_vm(vm_id, VMState.ACTIVE)
            await self._task_repository.update_task(task_id, TaskStatus.ACTIVE)
            logger.info("Finished VM provisioning task_id=%s vm_id=%s", task_id, vm_id)
        except Exception as exc:
            logger.exception("VM provisioning failed task_id=%s vm_id=%s", task_id, vm_id)
            await self._mark_provisioning_failed(task_id=task_id, vm_id=vm_id, error=str(exc))

    async def get_vm(self, vm_id: str) -> VMRead:
        try:
            return await self._repository.get_vm(vm_id)
        except AppError:
            raise
        except VMRepositoryNotFoundError as exc:
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryError as exc:
            logger.exception("VM fetch failed vm_id=%s", vm_id)
            raise VMOperationError("Unable to fetch VM at this time.") from exc

    async def get_vm_status(self, vm_id: str) -> VMStatusResponse:
        vm = await self.get_vm(vm_id)
        task = await self._task_repository.get_latest_for_vm(vm_id)
        return VMStatusResponse(vm=vm, task=task)

    async def get_task(self, task_id: str) -> TaskRead:
        return await self._task_repository.get_task(task_id)

    async def list_vms(self) -> list[VMRead]:
        try:
            return list(await self._repository.list_vms())
        except AppError:
            raise
        except VMRepositoryError as exc:
            logger.exception("VM list failed")
            raise VMOperationError("Unable to list VMs at this time.") from exc

    async def stop_vm(self, vm_id: str) -> VMRead:
        vm = await self.get_vm(vm_id)
        self._ensure_transition_allowed(vm.state, VMState.STOPPING)
        await self._transition_vm(vm_id, VMState.STOPPING)
        try:
            stopped = await self._repository.stop_vm(vm_id)
            return await self._transition_vm(stopped.id, VMState.STOPPED)
        except VMRepositoryError as exc:
            await self._transition_vm(vm_id, VMState.ERROR)
            raise VMOperationError("Unable to stop VM at this time.") from exc

    async def delete_vm(self, vm_id: str) -> VMRead:
        vm = await self.get_vm(vm_id)
        self._ensure_transition_allowed(vm.state, VMState.DELETING)
        await self._transition_vm(vm_id, VMState.DELETING)
        try:
            await self._repository.delete_vm(vm_id)
            return await self._transition_vm(vm_id, VMState.DELETED)
        except VMRepositoryNotFoundError as exc:
            raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except VMRepositoryError as exc:
            await self._transition_vm(vm_id, VMState.ERROR)
            raise VMOperationError("Unable to delete VM at this time.") from exc

    async def start_vm(self, vm_id: str) -> VMRead:
        vm = await self.get_vm(vm_id)
        if vm.state != VMState.STOPPED:
            raise VMInvalidStateError(f"Cannot start VM from '{vm.state}'.")
        try:
            return await self._repository.start_vm(vm_id)
        except VMRepositoryError as exc:
            raise VMOperationError("Unable to start VM at this time.") from exc

    async def _transition_vm(self, vm_id: str, target_state: VMState) -> VMRead:
        vm = await self.get_vm(vm_id)
        self._ensure_transition_allowed(vm.state, target_state)
        try:
            return await self._repository.update_vm_state(vm_id, target_state)
        except VMRepositoryError as exc:
            raise VMOperationError(f"Unable to transition VM to '{target_state}'.") from exc

    async def _mark_provisioning_failed(self, task_id: str, vm_id: str, error: str) -> None:
        try:
            vm = await self.get_vm(vm_id)
            if vm.state == VMState.PROVISIONING:
                await self._transition_vm(vm_id, VMState.ERROR)
        finally:
            await self._task_repository.update_task(task_id, TaskStatus.ERROR, error=error)

    def _ensure_transition_allowed(self, current: VMState, target: VMState) -> None:
        if target not in self._ALLOWED_TRANSITIONS[current]:
            raise VMInvalidStateError(f"Cannot transition VM from '{current}' to '{target}'.")
