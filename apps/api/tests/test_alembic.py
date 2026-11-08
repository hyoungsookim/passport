"""Runs Alembic in a subprocess: env.py reconfigures logging for the whole process."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.autogenerate import render_python_code
from alembic.operations import ops

from passport.db.base import Base, render_item
from passport.db.models import TenantMembership
from passport.settings.config import SettingsError, database_url, load_settings

API_DIR = Path(__file__).parents[1]


def alembic(*args, **env):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=os.environ | env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stops_on_settings_error(tmp_path):
    result = alembic("current", PASSPORT_CONFIG_PATH=str(tmp_path / "missing.json"))

    assert result.returncode != 0
    assert "SettingsError: Cannot read config file" in result.stderr


def test_offline_sql_needs_no_settings(tmp_path):
    result = alembic(
        "upgrade", "head", "--sql", PASSPORT_CONFIG_PATH=str(tmp_path / "missing.json")
    )

    assert result.returncode == 0, result.stderr


def test_autogenerate_renders_int_enum_columns_as_smallint():
    upgrade = ops.UpgradeOps(
        [ops.CreateTableOp.from_table(t) for t in Base.metadata.sorted_tables]
    )

    code = render_python_code(upgrade, render_item=render_item)

    assert "passport." not in code
    table = TenantMembership.__tablename__
    assert f"op.create_table('{table}'" in code
    assert "sa.Column('membership_status', sa.SmallInteger()," in code


def test_metadata_matches_database():
    try:
        database = load_settings().database
        database_url(database, "PASSPORT_DB_OWNERNAME", "PASSPORT_DB_OWNER_PASSWORD")
    except SettingsError as e:
        pytest.skip(f"migration database not configured: {e}")

    result = alembic("check")

    assert result.returncode == 0, result.stderr
    assert "No new upgrade operations detected" in result.stdout + result.stderr
