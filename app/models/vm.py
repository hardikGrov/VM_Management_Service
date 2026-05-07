from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class VMState(StrEnum):
    PROVISIONED = "provisioned"
    RUNNING = "running"
    STOPPED = "stopped"


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
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid4()),
            name=payload.name,
            image=payload.image,
            cpu_count=payload.cpu_count,
            memory_mb=payload.memory_mb,
            region=payload.region,
            state=VMState.PROVISIONED,
            created_at=now,
            updated_at=now,
        )


class VMOperationResponse(BaseModel):
    message: str = Field(description="Result of the requested lifecycle operation.")
    vm: VMRead

