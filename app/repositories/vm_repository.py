from collections.abc import Iterable
from copy import deepcopy
from threading import RLock
from typing import Protocol

from app.models.vm import VMCreate, VMRecord


class VMRepositoryError(Exception):
    """Base exception for VM repository/provider failures."""


class VMRepositoryNotFoundError(VMRepositoryError):
    """Raised when the VM provider cannot find the requested VM."""


class VMRepositoryConflictError(VMRepositoryError):
    """Raised when the VM provider rejects the requested operation."""


class VMRepository(Protocol):
    def create(self, payload: VMCreate) -> VMRecord: ...

    def list(self) -> Iterable[VMRecord]: ...

    def get(self, vm_id: str) -> VMRecord: ...

    def delete(self, vm_id: str) -> None: ...


class InMemoryVMRepository:
    def __init__(self) -> None:
        self._items: dict[str, VMRecord] = {}
        self._lock = RLock()

    def create(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        with self._lock:
            self._items[vm.id] = vm
            return deepcopy(vm)

    def list(self) -> Iterable[VMRecord]:
        with self._lock:
            return [deepcopy(vm) for vm in self._items.values()]

    def get(self, vm_id: str) -> VMRecord:
        with self._lock:
            vm = self._items.get(vm_id)
            if vm is None:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            return deepcopy(vm)

    def delete(self, vm_id: str) -> None:
        with self._lock:
            if vm_id not in self._items:
                raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
            del self._items[vm_id]
