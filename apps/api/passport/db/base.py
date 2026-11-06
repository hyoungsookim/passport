"""Declarative base shared by all ORM models."""

from datetime import datetime
from enum import IntEnum
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, SmallInteger, TypeDecorator
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # All timestamps are timestamptz (DB_MODEL.md 1).
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}

    # Fixed constraint names so Alembic can alter and drop them reliably.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class IntEnumType[E: IntEnum](TypeDecorator[E]):
    """Stores an IntEnum as its smallint key; unknown keys raise ValueError."""

    impl = SmallInteger
    cache_ok = True

    def __init__(self, enum_class: type[E]) -> None:
        super().__init__()
        self.enum_class = enum_class

    def process_bind_param(self, value: E | None, dialect: Dialect) -> int | None:
        return None if value is None else self.enum_class(value).value

    def process_result_value(self, value: int | None, dialect: Dialect) -> E | None:
        return None if value is None else self.enum_class(value)
