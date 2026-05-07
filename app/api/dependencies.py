from functools import lru_cache

from app.repositories.vm_repository import InMemoryVMRepository, VMRepository
from app.services.vm_service import VMService


@lru_cache
def get_vm_repository() -> VMRepository:
    return InMemoryVMRepository()


def get_vm_service() -> VMService:
    return VMService(repository=get_vm_repository())

