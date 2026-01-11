from __future__ import annotations


def split_emails(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(',') if x.strip()]
