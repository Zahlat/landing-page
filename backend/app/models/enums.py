"""Fixed value sets, stored as VARCHAR + CHECK (never native PG ENUMs).

Only the codes live in the DB/API; human labels live in src/content/{en,ar}.ts.
"""

from enum import StrEnum
from typing import Any

import sqlalchemy as sa


class MessageType(StrEnum):
    SUGGESTION = "suggestion"
    REQUEST = "request"
    QUESTION = "question"
    OTHER = "other"


class MessageStatus(StrEnum):
    NEW = "new"
    READ = "read"
    ARCHIVED = "archived"


class Locale(StrEnum):
    AR = "ar"
    EN = "en"


def str_enum_column_type(enum_cls: type[StrEnum], *, name: str, length: int) -> sa.Enum:
    """VARCHAR(length) + CHECK (col IN (...values)).

    values_callable makes SQLAlchemy store the *value* ("request"), not the member
    name ("REQUEST").
    """

    def values(e: Any) -> list[str]:
        return [m.value for m in e]

    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=values,
        validate_strings=True,
    )
