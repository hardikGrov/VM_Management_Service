import datetime
from copy import deepcopy
from threading import RLock

from app.models.vm import TaskRead, TaskRecord, TaskStatus


class TaskRepository:
    def __init__(self) -> None:
        self._items: dict[str, TaskRecord] = {}
        self._lock = RLock()

    async def create_task(self, vm_id: str, status: TaskStatus) -> TaskRecord:
        task = TaskRecord.create(vm_id=vm_id, status=status)
        with self._lock:
            self._items[task.task_id] = task
            return deepcopy(task)

    async def get_task(self, task_id: str) -> TaskRead:
        with self._lock:
            task = self._items.get(task_id)
            if task is None:
                from app.core.exceptions import VMNotFoundError

                raise VMNotFoundError(f"Task '{task_id}' was not found.")
            return deepcopy(task)

    async def get_latest_for_vm(self, vm_id: str) -> TaskRead | None:
        with self._lock:
            tasks = [task for task in self._items.values() if task.vm_id == vm_id]
            if not tasks:
                return None
            return deepcopy(max(tasks, key=lambda task: task.created_at))

    async def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        error: str | None = None,
    ) -> TaskRecord:
        with self._lock:
            task = self._items.get(task_id)
            if task is None:
                from app.core.exceptions import VMNotFoundError

                raise VMNotFoundError(f"Task '{task_id}' was not found.")
            updated = task.model_copy(
                update={
                    "status": status,
                    "error": error,
                    "updated_at": datetime.datetime.now(datetime.UTC),
                }
            )
            self._items[task_id] = updated
            return deepcopy(updated)
