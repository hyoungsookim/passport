import json

import pytest

from passport.settings.config import SettingsError, database_url, load_settings

DATABASE = {
    "host": "db",
    "port": 5432,
    "name": "passport",
    "pool_size": 5,
    "pool_timeout": 30,
}


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "custom.json"
    path.write_text(json.dumps({"database": DATABASE}))
    return path


def test_loads_file_from_config_path_env(monkeypatch, config_file):
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(config_file))

    assert load_settings().database.model_dump() == DATABASE


@pytest.mark.parametrize("value", [None, ""])
def test_defaults_to_config_json_in_cwd(monkeypatch, tmp_path, config_file, value):
    config_file.rename(tmp_path / "config.json")
    monkeypatch.chdir(tmp_path)
    if value is None:
        monkeypatch.delenv("PASSPORT_CONFIG_PATH", raising=False)
    else:
        monkeypatch.setenv("PASSPORT_CONFIG_PATH", value)

    assert load_settings().database.name == "passport"


def test_missing_env_path_does_not_fall_back_to_cwd(monkeypatch, tmp_path, config_file):
    config_file.rename(tmp_path / "config.json")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(tmp_path / "missing.json"))

    with pytest.raises(SettingsError, match="Cannot read config file .*missing.json"):
        load_settings()


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        json.dumps({}),
        json.dumps({"database": DATABASE | {"pool_size": 0}}),
        json.dumps({"database": DATABASE | {"port": 70000}}),
        json.dumps({"database": DATABASE | {"unknown": 1}}),
    ],
)
def test_invalid_config_raises(monkeypatch, config_file, content):
    config_file.write_text(content)
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(config_file))

    with pytest.raises(SettingsError, match="Invalid config file"):
        load_settings()


def test_database_url_uses_credentials_from_env(monkeypatch, config_file):
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("USER_ENV", "app")
    monkeypatch.setenv("PASSWORD_ENV", "p@ss")

    url = database_url(load_settings().database, "USER_ENV", "PASSWORD_ENV")

    assert url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://app:p%40ss@db:5432/passport"
    )


def test_database_url_requires_credentials(monkeypatch, config_file):
    monkeypatch.setenv("PASSPORT_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("USER_ENV", "app")
    monkeypatch.delenv("PASSWORD_ENV", raising=False)

    with pytest.raises(SettingsError, match="USER_ENV and PASSWORD_ENV must be set"):
        database_url(load_settings().database, "USER_ENV", "PASSWORD_ENV")
