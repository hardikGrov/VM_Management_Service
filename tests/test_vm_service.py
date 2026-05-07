import pytest

from app.core.exceptions import VMNotFoundError, VMProviderError
from app.models.vm import VMCreate, VMRecord
from app.repositories.vm_repository import VMRepositoryError, VMRepositoryNotFoundError
from app.services.vm_service import VMService


class FakeVMRepository:
    def __init__(self) -> None:
        self.items: dict[str, VMRecord] = {}

    def create(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        self.items[vm.id] = vm
        return vm

    def list(self) -> list[VMRecord]:
        return list(self.items.values())

    def get(self, vm_id: str) -> VMRecord:
        try:
            return self.items[vm_id]
        except KeyError as exc:
            raise VMRepositoryNotFoundError from exc

    def delete(self, vm_id: str) -> None:
        if vm_id not in self.items:
            raise VMRepositoryNotFoundError
        del self.items[vm_id]


def test_service_creates_gets_and_deletes_vm() -> None:
    service = VMService(repository=FakeVMRepository())
    payload = VMCreate(name="api-01", image="ubuntu-24.04", cpu_count=2, memory_mb=4096)

    created = service.create_vm(payload)
    fetched = service.get_vm(created.id)
    deleted = service.delete_vm(created.id)

    assert fetched.id == created.id
    assert deleted.id == created.id
    with pytest.raises(VMNotFoundError):
        service.get_vm(created.id)


def test_service_maps_provider_errors() -> None:
    class FailingRepository(FakeVMRepository):
        def create(self, payload: VMCreate) -> VMRecord:
            raise VMRepositoryError("provider unavailable")

    service = VMService(repository=FailingRepository())

    with pytest.raises(VMProviderError):
        service.create_vm(
            VMCreate(name="api-01", image="ubuntu-24.04", cpu_count=2, memory_mb=4096)
        )
