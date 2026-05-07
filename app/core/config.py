from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VM Management Service"
    environment: Literal["local", "dev", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    vm_repository_backend: Literal["memory", "openstack"] = "memory"

    os_auth_url: str | None = None
    os_username: str | None = None
    os_password: str | None = None
    os_project_name: str | None = None
    os_user_domain_name: str = "Default"
    os_project_domain_name: str = "Default"
    os_region_name: str | None = None
    os_network_name: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
