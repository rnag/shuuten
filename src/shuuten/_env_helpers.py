from __future__ import annotations

import logging
from enum import Enum
from typing import TypeVar


E = TypeVar('E', bound=Enum)


def split_emails(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(',') if x.strip()]


def parse_enum(v: str | None, *, enum: type[E], default: E) -> E:
    if v is None:
        return default

    s = v.strip().lower()

    # match by value (recommended for env vars)
    for member in enum:
        if member.value == s:
            return member

    # fallback: match by name (BLOCKS / PLAIN)
    try:
        return enum[s.upper()]
    except KeyError:
        return default


def parse_bool(v: str | None, *, default: bool) -> bool:
    if v is None:
        return default

    s = v.strip().upper()
    if s in ('0', 'FALSE', 'NO', 'OFF', 'DISABLE'):
        return False

    if s in ('1', 'TRUE', 'YES', 'ON', 'ENABLE'):
        return True

    return default


def parse_level(v: str | None, *, default: int) -> int:
    if not v:
        return default
    s = v.strip().upper()
    if s.isdigit():
        return int(s)
    # noinspection PyUnresolvedReferences,PyProtectedMember
    return logging._nameToLevel.get(s, default)


def parse_quiet(v: str | None, *, default_level: int):
    if v is None:
        return default_level

    s = v.strip().upper()

    if s in ('0', 'FALSE', 'NO', 'OFF', 'NONE', 'DISABLE'):
        return None

    if s.isdigit():
        return int(s)

    # noinspection PyUnresolvedReferences,PyProtectedMember
    lvl = logging._nameToLevel.get(s)

    if lvl is not None:
        return lvl

    return default_level
