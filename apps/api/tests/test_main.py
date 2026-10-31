import json

import pytest
from fastapi.testclient import TestClient

from passport.main import create_app
from passport.settings.config import SettingsError


@pytest.fixture
def db_env(monkeypatch, tmp_path):
    config = tmp_path / "config.json"
    database = {"host": "db", "port": 5432, "name": "passport"}
    config.write_text(
        json.dumps({"database": database | {"pool_size": 3, "pool_timeout": 2}})
    )
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(config))
    monkeypatch.setenv("PASSPORT_DB_USERNAME", "app")
    monkeypatch.setenv("PASSPORT_DB_PASSWORD", "secret")


def test_startup_creates_engine_from_settings(db_env):
    app = create_app()

    with TestClient(app):
        engine = app.state.session_factory.kw["bind"]
        assert engine.url.username == "app"
        assert engine.url.host == "db"
        assert engine.pool.size() == 3


def test_startup_stops_on_settings_error(monkeypatch, tmp_path):
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(tmp_path / "missing.json"))

    with (
        pytest.raises(SettingsError, match="Cannot read config file"),
        TestClient(create_app()),
    ):
        pass
