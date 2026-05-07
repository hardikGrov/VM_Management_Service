from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from functools import lru_cache
from time import perf_counter
from typing import Any, TypeVar

from app.core.config import Settings
from app.core.exceptions import VMNotFoundError, VMOperationError
from app.models.vm import VMCreate, VMRecord, VMState

logger = logging.getLogger(__name__)

T = TypeVar("T")


@lru_cache(maxsize=8)
def get_connection(
    auth_url: str,
    username: str,
    password: str,
    project_name: str,
    user_domain_name: str = "Default",
    project_domain_name: str = "Default",
    region_name: str | None = None,
) -> Any:
    """Return a cached openstacksdk connection for the given credential set."""
    try:
        import openstack
    except ImportError as exc:
        raise VMOperationError("openstacksdk is not installed.") from exc

    return openstack.connect(
        auth_url=auth_url,
        username=username,
        password=password,
        project_name=project_name,
        user_domain_name=user_domain_name,
        project_domain_name=project_domain_name,
        region_name=region_name,
        app_name="vm-management-service",
    )


class OpenStackVMAdapter:
    """Async VM repository adapter backed by openstacksdk.

    openstacksdk is synchronous, so every OpenStack API call is executed through
    `asyncio.to_thread()` to avoid blocking the FastAPI event loop.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection = self._build_connection(settings)
        self._compute = self._connection.compute
        self._network = self._connection.network
        self._storage = self._connection.block_storage
        self._reserved: dict[str, VMRecord] = {}
        self._provider_ids: dict[str, str] = {}

    async def create_vm(self, payload: VMCreate) -> VMRecord:
        image = await self._find_image(payload.image)
        flavor = await self._find_flavor(payload.cpu_count, payload.memory_mb)
        networks = await self._build_networks()

        server = await self._call(
            "create_server",
            None,
            self._compute.create_server,
            name=payload.name,
            image_id=image.id,
            flavor_id=flavor.id,
            networks=networks or None,
        )
        server = await self._call(
            "wait_for_server",
            server.id,
            self._compute.wait_for_server,
            server,
        )
        return self._server_to_domain(server, fallback=payload, flavor=flavor)

    async def reserve_vm(self, payload: VMCreate) -> VMRecord:
        vm = VMRecord.create(payload)
        self._reserved[vm.id] = vm
        return vm

    async def provision_vm(self, vm_id: str, payload: VMCreate) -> VMRecord:
        created = await self.create_vm(payload)
        self._provider_ids[vm_id] = created.id
        reserved = created.model_copy(update={"id": vm_id, "state": VMState.PROVISIONING})
        self._reserved[vm_id] = reserved
        return reserved

    async def get_vm(self, vm_id: str) -> VMRecord:
        if vm_id in self._reserved:
            return self._reserved[vm_id]
        server = await self._get_server(vm_id)
        flavor = await self._get_server_flavor(server)
        return self._server_to_domain(server, flavor=flavor)

    async def list_vms(self) -> Iterable[VMRecord]:
        servers = await self._call("list_servers", None, lambda: list(self._compute.servers()))
        records: list[VMRecord] = []
        for server in servers:
            flavor = await self._get_server_flavor(server)
            records.append(self._server_to_domain(server, flavor=flavor))
        return records

    async def delete_vm(self, vm_id: str) -> None:
        provider_id = self._provider_ids.get(vm_id, vm_id)
        server = await self._get_server(provider_id)
        await self._call(
            "delete_server",
            vm_id,
            self._compute.delete_server,
            server,
            ignore_missing=False,
        )

    async def start_vm(self, vm_id: str) -> VMRecord:
        provider_id = self._provider_ids.get(vm_id, vm_id)
        server = await self._get_server(provider_id)
        await self._call("start_server", vm_id, self._compute.start_server, server)
        server = await self._call("wait_for_server", vm_id, self._compute.wait_for_server, server)
        flavor = await self._get_server_flavor(server)
        vm = self._server_to_domain(server, flavor=flavor).model_copy(update={"id": vm_id})
        self._reserved[vm_id] = vm
        return vm

    async def stop_vm(self, vm_id: str) -> VMRecord:
        provider_id = self._provider_ids.get(vm_id, vm_id)
        server = await self._get_server(provider_id)
        await self._call("stop_server", vm_id, self._compute.stop_server, server)
        server = await self._call("wait_for_server", vm_id, self._compute.wait_for_server, server)
        flavor = await self._get_server_flavor(server)
        vm = self._server_to_domain(server, flavor=flavor).model_copy(update={"id": vm_id})
        self._reserved[vm_id] = vm
        return vm

    async def update_vm_state(self, vm_id: str, state: VMState) -> VMRecord:
        vm = await self.get_vm(vm_id)
        updated = vm.model_copy(update={"state": state, "updated_at": datetime.now(UTC)})
        self._reserved[vm_id] = updated
        return updated

    async def create(self, payload: VMCreate) -> VMRecord:
        return await self.create_vm(payload)

    async def get(self, vm_id: str) -> VMRecord:
        return await self.get_vm(vm_id)

    async def list(self) -> Iterable[VMRecord]:
        return await self.list_vms()

    async def delete(self, vm_id: str) -> None:
        await self.delete_vm(vm_id)

    @staticmethod
    def _build_connection(settings: Settings) -> Any:
        required = {
            "OS_AUTH_URL": settings.os_auth_url,
            "OS_USERNAME": settings.os_username,
            "OS_PASSWORD": settings.os_password,
            "OS_PROJECT_NAME": settings.os_project_name,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise VMOperationError(f"Missing OpenStack configuration: {', '.join(missing)}.")

        return get_connection(
            auth_url=settings.os_auth_url,
            username=settings.os_username,
            password=settings.os_password,
            project_name=settings.os_project_name,
            user_domain_name=settings.os_user_domain_name,
            project_domain_name=settings.os_project_domain_name,
            region_name=settings.os_region_name,
        )

    async def _get_server(self, vm_id: str) -> Any:
        server = await self._call("get_server", vm_id, self._compute.get_server, vm_id)
        if server is None:
            raise VMNotFoundError(f"VM '{vm_id}' was not found.")
        return server

    async def _find_image(self, image_name_or_id: str) -> Any:
        image = await self._call(
            "find_image",
            None,
            self._compute.find_image,
            image_name_or_id,
            ignore_missing=True,
        )
        if image is None:
            raise VMOperationError(f"OpenStack image '{image_name_or_id}' was not found.")
        return image

    async def _find_flavor(self, cpu_count: int, memory_mb: int) -> Any:
        flavors = await self._call("list_flavors", None, lambda: list(self._compute.flavors()))
        for flavor in flavors:
            flavor_vcpus = int(getattr(flavor, "vcpus", 0))
            flavor_memory = int(getattr(flavor, "ram", 0))
            if flavor_vcpus == cpu_count and flavor_memory == memory_mb:
                return flavor
        raise VMOperationError(
            f"No OpenStack flavor matches cpu_count={cpu_count}, memory_mb={memory_mb}."
        )

    async def _build_networks(self) -> list[dict[str, str]]:
        if not self._settings.os_network_name:
            return []

        network = await self._call(
            "find_network",
            None,
            self._network.find_network,
            self._settings.os_network_name,
            ignore_missing=True,
        )
        if network is None:
            raise VMOperationError(
                f"OpenStack network '{self._settings.os_network_name}' was not found."
            )
        return [{"uuid": network.id}]

    async def _get_server_flavor(self, server: Any) -> Any | None:
        flavor_id = self._extract_flavor_id(server)
        if not flavor_id:
            return None
        return await self._call(
            "get_flavor",
            getattr(server, "id", None),
            self._compute.get_flavor,
            flavor_id,
        )

    async def _call(
        self,
        operation: str,
        vm_id: str | None,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        start = perf_counter()
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except VMNotFoundError:
            raise
        except Exception as exc:
            if self._is_not_found_error(exc):
                raise VMNotFoundError(f"VM '{vm_id}' was not found.") from exc
            raise VMOperationError(f"OpenStack operation '{operation}' failed.") from exc
        finally:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            logger.info(
                "openstack_api_call",
                extra={
                    "operation": operation,
                    "vm_id": vm_id,
                    "duration_ms": duration_ms,
                },
            )

    @staticmethod
    def _server_to_domain(
        server: Any,
        fallback: VMCreate | None = None,
        flavor: Any | None = None,
    ) -> VMRecord:
        now = datetime.now(UTC)
        image = getattr(server, "image", None)
        image_name = OpenStackVMAdapter._extract_resource_name(
            image,
            fallback.image if fallback else "",
        )

        return VMRecord(
            id=str(server.id),
            name=str(getattr(server, "name", fallback.name if fallback else "")),
            image=image_name,
            cpu_count=int(getattr(flavor, "vcpus", fallback.cpu_count if fallback else 1)),
            memory_mb=int(getattr(flavor, "ram", fallback.memory_mb if fallback else 512)),
            region=str(getattr(server, "region", fallback.region if fallback else "unknown")),
            state=OpenStackVMAdapter._normalize_state(getattr(server, "status", None)),
            created_at=(
                OpenStackVMAdapter._parse_datetime(getattr(server, "created_at", None)) or now
            ),
            updated_at=(
                OpenStackVMAdapter._parse_datetime(getattr(server, "updated_at", None)) or now
            ),
        )

    @staticmethod
    def _extract_flavor_id(server: Any) -> str | None:
        flavor = getattr(server, "flavor", None)
        if isinstance(flavor, dict):
            return flavor.get("id") or flavor.get("original_name")
        return getattr(flavor, "id", None) if flavor else None

    @staticmethod
    def _extract_resource_name(resource: Any, default: str) -> str:
        if isinstance(resource, dict):
            return str(resource.get("name") or resource.get("id") or default)
        return str(getattr(resource, "name", None) or getattr(resource, "id", None) or default)

    @staticmethod
    def _normalize_state(status: Any) -> VMState:
        status_value = str(status or "").lower()
        status_map = {
            "active": VMState.ACTIVE,
            "running": VMState.ACTIVE,
            "shutoff": VMState.STOPPED,
            "stopped": VMState.STOPPED,
            "paused": VMState.STOPPED,
            "building": VMState.PROVISIONING,
            "build": VMState.PROVISIONING,
            "provisioned": VMState.ACTIVE,
        }
        return status_map.get(status_value, VMState.PENDING)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _is_not_found_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
        return status_code == 404 or exc.__class__.__name__ in {
            "NotFoundException",
            "ResourceNotFound",
            "NotFound",
        }
