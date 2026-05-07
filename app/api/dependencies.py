from functools import lru_cache

from app.core.config import get_settings
from app.repositories.openstack_adapter import OpenStackVMAdapter
from app.repositories.task_repository import TaskRepository
from app.repositories.vm_repository import InMemoryVMRepository, VMRepository
from app.services.vm_service import VMService


@lru_cache
def get_vm_repository() -> VMRepository:
    settings = get_settings()
    if settings.vm_repository_backend == "openstack":
        return OpenStackVMAdapter(settings=settings)
    return InMemoryVMRepository()


@lru_cache
def get_task_repository() -> TaskRepository:
    return TaskRepository()


def get_vm_service() -> VMService:
    return VMService(repository=get_vm_repository(), task_repository=get_task_repository())
