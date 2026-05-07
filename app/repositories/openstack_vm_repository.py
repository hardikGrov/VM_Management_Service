from datetime import UTC, datetime
from typing import Any

from app.models.vm import VMCreate, VMRecord, VMState
from app.repositories.vm_repository import (
    VMRepositoryConflictError,
    VMRepositoryError,
    VMRepositoryNotFoundError,
)


class OpenStackVMRepository:
    """Repository adapter for an OpenStack compute client.

    The injected client is expected to expose `create_server`, `get_server`, and
    `delete_server`. This keeps the service decoupled from a concrete SDK while
    still making OpenStack the infrastructure boundary.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, payload: VMCreate) -> VMRecord:
        try:
            server = self._client.create_server(
                name=payload.name,
                image=payload.image,
                cpu_count=payload.cpu_count,
                memory_mb=payload.memory_mb,
                region=payload.region,
            )
        except ValueError as exc:
            raise VMRepositoryConflictError(str(exc)) from exc
        except Exception as exc:
            raise VMRepositoryError("OpenStack failed to create VM.") from exc

        return self._to_record(server, fallback=payload)

    def get(self, vm_id: str) -> VMRecord:
        try:
            server = self._client.get_server(vm_id)
        except KeyError as exc:
            raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except Exception as exc:
            raise VMRepositoryError("OpenStack failed to fetch VM.") from exc

        if server is None:
            raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")
        return self._to_record(server)

    def delete(self, vm_id: str) -> None:
        try:
            deleted = self._client.delete_server(vm_id)
        except KeyError as exc:
            raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.") from exc
        except Exception as exc:
            raise VMRepositoryError("OpenStack failed to delete VM.") from exc

        if deleted is False:
            raise VMRepositoryNotFoundError(f"VM '{vm_id}' was not found.")

    @staticmethod
    def _to_record(server: Any, fallback: VMCreate | None = None) -> VMRecord:
        now = datetime.now(UTC)
        created_at = getattr(server, "created_at", None) or getattr(server, "created", None) or now
        updated_at = getattr(server, "updated_at", None) or getattr(server, "updated", None) or now

        return VMRecord(
            id=str(server.id),
            name=str(getattr(server, "name", fallback.name if fallback else "")),
            image=str(getattr(server, "image", fallback.image if fallback else "")),
            cpu_count=int(getattr(server, "cpu_count", fallback.cpu_count if fallback else 1)),
            memory_mb=int(getattr(server, "memory_mb", fallback.memory_mb if fallback else 512)),
            region=str(getattr(server, "region", fallback.region if fallback else "unknown")),
            state=OpenStackVMRepository._normalize_state(getattr(server, "state", None)),
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _normalize_state(state: Any) -> VMState:
        if isinstance(state, VMState):
            return state

        state_value = str(state or "").lower()
        provider_state_map = {
            "active": VMState.ACTIVE,
            "running": VMState.ACTIVE,
            "shutoff": VMState.STOPPED,
            "stopped": VMState.STOPPED,
            "paused": VMState.STOPPED,
            "building": VMState.PROVISIONING,
            "provisioned": VMState.ACTIVE,
        }
        return provider_state_map.get(state_value, VMState.PENDING)
