from __future__ import annotations

import re
from typing import Any

DEFAULT_SENSITIVE_KEYS = frozenset({
    'token',
    'access_token',
    'refresh_token',
    'id_token',
    'auth',
    'authorization',
    'password',
    'pwd',
    'passphrase',
    'secret',
    'client_secret',
    'secret_key',
    'private_key',
    'api_key',
    'x-api-key',
    'x_api_key',
    'cookie',
    'set-cookie',
    'set_cookie',
    'session',
    'aws_access_key_id',
    'aws_secret_access_key',
    'aws_session_token',
})

BEARER_RE = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9\-_.=]+\b')


def redact_optional(s: str | None) -> str | None:
    return redact(s) if s else None


def redact(value: Any,
           *,
           sensitive_keys: object = DEFAULT_SENSITIVE_KEYS,
           max_len: int = 4000) -> Any:

    # skip "falsy" values
    if not value:
        return value

    # string
    if isinstance(value, str):
        s = BEARER_RE.sub('Bearer [REDACTED]', value)
        if len(s) > max_len:
            return s[:max_len] + '…[TRUNCATED]'
        return s

    # dict
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if str(k).lower() in sensitive_keys:
                out[k] = '[REDACTED]'
            else:
                out[k] = redact(
                    v,
                    sensitive_keys=sensitive_keys,
                    max_len=max_len,
                )
        return out

    # list/tuple
    if isinstance(value, (list, tuple)):
        return [redact(v, sensitive_keys=sensitive_keys, max_len=max_len)
                for v in value]

    # other scalars
    return value
