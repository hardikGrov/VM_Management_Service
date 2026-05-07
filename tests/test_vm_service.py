import asyncio

import pytest

from app.core.exceptions import VMInvalidStateError, VMOperationError
from app.models.vm import TaskStatus, VMCreate, VMRecord, VMState
from app.repositories.task_repository import TaskRepository
from app.repositories.vm_repository import VMRepositoryError, VMRepositoryNotFoundError
from app.services.vm_service import VMService


class FakeVMRepository:
    def __init__(self) -> None:
        self.items: dict[str, VMRecord] = {}

    async def create_vm(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        vm = vm.model_copy(update={"state": VMState.ACTIVE})
        self.items[vm.id] = vm
        return vm

    async def reserve_vm(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        self.items[vm.id] = vm
        return vm

    async def provision_vm(self, vm_id: str, payload: VMCreate) -> VMRecord:
        return await self.get_vm(vm_id)

    async def list_vms(self) -> list[VMRecord]:
        return list(self.items.values())

    async def get_vm(self, vm_id: str) -> VMRecord:
        try:
            return self.items[vm_id]
        except KeyError as exc:
            raise VMRepositoryNotFoundError from exc

    async def delete_vm(self, vm_id: str) -> None:
        if vm_id not in self.items:
            raise VMRepositoryNotFoundError

    async def start_vm(self, vm_id: str) -> VMRecord:
        return await self.get_vm(vm_id)

    async def stop_vm(self, vm_id: str) -> VMRecord:
        return await self.get_vm(vm_id)

    async def update_vm_state(self, vm_id: str, state: VMState) -> VMRecord:
        vm = await self.get_vm(vm_id)
        updated = vm.model_copy(update={"state": state})
        self.items[vm_id] = updated
        return updated


def test_service_creates_gets_and_deletes_vm() -> None:
    async def run_test() -> None:
        service = VMService(repository=FakeVMRepository(), task_repository=TaskRepository())
        payload = VMCreate(name="api-01", image="ubuntu-24.04", cpu_count=2, memory_mb=4096)

        created = await service.create_vm(payload)
        await service.provision_vm(created.task_id, created.vm_id, payload)
        fetched = await service.get_vm(created.vm_id)
        deleted = await service.delete_vm(created.vm_id)

        assert fetched.id == created.vm_id
        assert deleted.id == created.vm_id
        assert deleted.state == VMState.DELETED

    asyncio.run(run_test())


def test_service_maps_provider_errors() -> None:
    async def run_test() -> None:
        class FailingRepository(FakeVMRepository):
            async def reserve_vm(self, payload: VMCreate) -> VMRecord:
                raise VMRepositoryError("provider unavailable")

        service = VMService(repository=FailingRepository(), task_repository=TaskRepository())

        with pytest.raises(VMOperationError):
            await service.create_vm(
                VMCreate(name="api-01", image="ubuntu-24.04", cpu_count=2, memory_mb=4096)
            )

    asyncio.run(run_test())


def test_service_rejects_invalid_stop_transition() -> None:
    async def run_test() -> None:
        service = VMService(repository=FakeVMRepository(), task_repository=TaskRepository())
        payload = VMCreate(name="api-01", image="ubuntu-24.04", cpu_count=2, memory_mb=4096)
        accepted = await service.create_vm(payload)

        with pytest.raises(VMInvalidStateError):
            await service.stop_vm(accepted.vm_id)

    asyncio.run(run_test())


def test_service_marks_failed_provisioning_task() -> None:
    async def run_test() -> None:
        class FailingProvisionRepository(FakeVMRepository):
            async def provision_vm(self, vm_id: str, payload: VMCreate) -> VMRecord:
                raise VMRepositoryError("quota exceeded")

        task_repository = TaskRepository()
        service = VMService(
            repository=FailingProvisionRepository(),
            task_repository=task_repository,
        )
        payload = VMCreate(name="api-01", image="ubuntu-24.04", cpu_count=2, memory_mb=4096)
        accepted = await service.create_vm(payload)

        await service.provision_vm(accepted.task_id, accepted.vm_id, payload)

        task = await service.get_task(accepted.task_id)
        status = await service.get_vm_status(accepted.vm_id)
        assert task.status == TaskStatus.ERROR
        assert task.error is not None
        assert status.vm.state == VMState.ERROR

    asyncio.run(run_test())
