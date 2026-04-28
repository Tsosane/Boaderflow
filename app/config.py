from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "BorderFlow"
    environment: str = "development"
    site_code: str = "DEPOT-MSU"
    site_name: str = "Maseru Depot"
    database_url: str = "sqlite:///./borderflow.db"
    redis_url: str = "redis://localhost:6379/0"
    api_secret_key: str = "change-me"
    repl_publications: str = ""
    repl_subscriptions: str = ""
    replication_user: str = "repl_user"
    replication_password: str = "repl_pass"
    topology_path: str = "infra/replication_topology.json"
    bootstrap_database: bool = True
    seed_scope: Literal["all", "depot_only", "none"] = "all"
    seed_password: str = "borderflow123"
    replication_stale_after_seconds: int = 300
    database_wait_timeout_seconds: int = 120
    database_wait_interval_seconds: int = 3
    page_size: int = 25
    session_cookie_name: str = "borderflow_session"
    control_tower_site_code: str = "CTRL-TOWER"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    route_base: str = "/"
    worker_refresh_interval_seconds: int = Field(default=60, ge=15)
    worker_health_interval_seconds: int = Field(default=90, ge=30)

    @property
    def publication_names(self) -> list[str]:
        return [item.strip() for item in self.repl_publications.split(",") if item.strip()]

    @property
    def subscription_names(self) -> list[str]:
        return [item.strip() for item in self.repl_subscriptions.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
