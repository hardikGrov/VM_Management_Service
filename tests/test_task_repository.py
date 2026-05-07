import asyncio

import pytest

from app.core.exceptions import VMNotFoundError
from app.models.vm import TaskStatus
from app.repositories.task_repository import TaskRepository


def test_task_repository_tracks_latest_task_for_vm() -> None:
    async def run_test() -> None:
        repository = TaskRepository()
        first = await repository.create_task("vm-1", TaskStatus.PROVISIONING)
        second = await repository.create_task("vm-1", TaskStatus.DELETING)

        await repository.update_task(first.task_id, TaskStatus.ACTIVE)

        latest = await repository.get_latest_for_vm("vm-1")
        assert latest is not None
        assert latest.task_id == second.task_id
        assert latest.status == TaskStatus.DELETING

    asyncio.run(run_test())


def test_task_repository_raises_for_missing_task() -> None:
    async def run_test() -> None:
        repository = TaskRepository()

        with pytest.raises(VMNotFoundError):
            await repository.get_task("missing")

    asyncio.run(run_test())
