from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class VMState(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DELETING = "deleting"
    DELETED = "deleted"


class VMBase(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="Display name for the VM.")
    image: str = Field(min_length=1, max_length=128, description="Base image identifier.")
    cpu_count: int = Field(ge=1, le=128, description="Number of vCPUs allocated.")
    memory_mb: int = Field(ge=512, le=1_048_576, description="Memory allocation in MiB.")


class VMCreate(VMBase):
    region: str = Field(default="us-east-1", min_length=1, max_length=64)


class VMResize(BaseModel):
    cpu_count: int = Field(ge=1, le=128, description="Updated number of vCPUs.")
    memory_mb: int = Field(ge=512, le=1_048_576, description="Updated memory allocation in MiB.")


class VMRead(VMBase):
    id: str = Field(description="Unique VM identifier.")
    region: str
    state: VMState
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VMRecord(VMRead):
    @classmethod
    def create(cls, payload: VMCreate) -> "VMRecord":
        now = datetime.now(UTC)
        return cls(
            id=str(uuid4()),
            name=payload.name,
            image=payload.image,
            cpu_count=payload.cpu_count,
            memory_mb=payload.memory_mb,
            region=payload.region,
            state=VMState.PENDING,
            created_at=now,
            updated_at=now,
        )


class VMCreateAccepted(BaseModel):
    task_id: str = Field(description="Provisioning task identifier.")
    vm_id: str = Field(description="Reserved VM identifier.")
    status: str = Field(description="Initial task status.")


class VMStatusResponse(BaseModel):
    vm: VMRead
    task: "TaskRead | None" = Field(
        default=None,
        description="Latest task associated with this VM.",
    )


class VMOperationResponse(BaseModel):
    message: str = Field(description="Result of the requested lifecycle operation.")
    vm: VMRead


class TaskStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DELETING = "deleting"
    DELETED = "deleted"


class TaskRead(BaseModel):
    task_id: str
    status: TaskStatus
    vm_id: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskRecord(TaskRead):
    @classmethod
    def create(cls, vm_id: str, status: TaskStatus) -> "TaskRecord":
        now = datetime.now(UTC)
        return cls(
            task_id=str(uuid4()),
            status=status,
            vm_id=vm_id,
            error=None,
            created_at=now,
            updated_at=now,
        )
