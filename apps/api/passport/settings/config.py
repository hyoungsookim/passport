"""Application settings loaded from config.json and environment variables."""

import os
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    ValidationError,
)
from sqlalchemy import URL


class SettingsError(Exception):
    pass


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str = Field(min_length=1)
    port: int = Field(gt=0, lt=65536)
    name: str = Field(min_length=1)
    pool_size: PositiveInt
    pool_timeout: PositiveFloat


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database: DatabaseSettings


def config_path() -> Path:
    return Path(os.environ.get("PASSPORT_CONFIG_PATH") or Path.cwd() / "config.json")


def load_settings() -> Settings:
    path = config_path()
    try:
        return Settings.model_validate_json(path.read_bytes())
    except OSError as e:
        raise SettingsError(f"Cannot read config file {path}: {e}") from e
    except ValidationError as e:
        raise SettingsError(f"Invalid config file {path}: {e}") from e


def database_url(
    database: DatabaseSettings, username_env: str, password_env: str
) -> URL:
    # Credentials stay in the environment so each process gets only its own account.
    username = os.environ.get(username_env)
    password = os.environ.get(password_env)
    if not username or not password:
        raise SettingsError(f"{username_env} and {password_env} must be set")
    return URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=database.host,
        port=database.port,
        database=database.name,
    )
