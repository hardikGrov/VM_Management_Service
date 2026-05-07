from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Protocol

from app.models.vm import VMCreate, VMRecord, VMState


class VMRepositoryError(Exception):
    """Base exception for VM repository/provider failures."""


class VMRepositoryNotFoundError(VMRepositoryError):
    """Raised when the VM provider cannot find the requested VM."""


class VMRepositoryConflictError(VMRepositoryError):
    """Raised when the VM provider rejects the requested operation."""


class VMRepository(Protocol):
    async def create_vm(self, payload: VMCreate) -> VMRecord: ...

    async def reserve_vm(self, payload: VMCreate) -> VMRecord: ...

    async def provision_vm(self, vm_id: str, payload: VMCreate) -> VMRecord: ...

    async def get_vm(self, vm_id: str) -> VMRecord: ...

    async def list_vms(self) -> Iterable[VMRecord]: ...

    async def delete_vm(self, vm_id: str) -> None: ...

    async def start_vm(self, vm_id: str) -> VMRecord: ...

    async def stop_vm(self, vm_id: str) -> VMRecord: ...

    async def update_vm_state(self, vm_id: str, state: VMState) -> VMRecord: ...


class InMemoryVMRepository:
    def __init__(self) -> None:
        self._items: dict[str, VMRecord] = {}
        self._lock = RLock()

    async def create_vm(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        vm = vm.model_copy(update={"state": VMState.ACTIVE})
        with self._lock:
            self._items[vm.id] = vm
            return deepcopy(vm)

    async def reserve_vm(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        with self._lock:
            self._items[vm.id] = vm
            return deepcopy(vm)

    async def provision_vm(self, vm_id: str, payload: VMCreate) -> VMRecord:
        with self._lock:
            vm = self._items.get(vm_id)
            if vm is None:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            return deepcopy(vm)

    async def list_vms(self) -> Iterable[VMRecord]:
        with self._lock:
            return [deepcopy(vm) for vm in self._items.values()]

    async def get_vm(self, vm_id: str) -> VMRecord:
        with self._lock:
            vm = self._items.get(vm_id)
            if vm is None:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            return deepcopy(vm)

    async def delete_vm(self, vm_id: str) -> None:
        with self._lock:
            if vm_id not in self._items:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")

    async def start_vm(self, vm_id: str) -> VMRecord:
        with self._lock:
            vm = self._items.get(vm_id)
            if vm is None:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            updated = vm.model_copy(
                update={"state": VMState.ACTIVE, "updated_at": datetime.now(timezone.utc)}
            )
            self._items[vm_id] = updated
            return deepcopy(updated)

    async def stop_vm(self, vm_id: str) -> VMRecord:
        with self._lock:
            vm = self._items.get(vm_id)
            if vm is None:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            return deepcopy(vm)

    async def update_vm_state(self, vm_id: str, state: VMState) -> VMRecord:
        with self._lock:
            vm = self._items.get(vm_id)
            if vm is None:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            updated = vm.model_copy(update={"state": state, "updated_at": datetime.now(timezone.utc)})
            self._items[vm_id] = updated
            return deepcopy(updated)

    async def create(self, payload: VMCreate) -> VMRecord:
        return await self.create_vm(payload)

    async def list(self) -> Iterable[VMRecord]:
        return await self.list_vms()

    async def get(self, vm_id: str) -> VMRecord:
        return await self.get_vm(vm_id)

    async def delete(self, vm_id: str) -> None:
        await self.delete_vm(vm_id)
