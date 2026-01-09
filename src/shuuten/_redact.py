import re
from typing import Any


DEFAULT_SENSITIVE_KEYS = frozenset((
    'token',
    'access_token',
    'refresh_token',
    'authorization',
    'pwd',
    'password',
    'secret',
    'client_secret',
    'cookie',
    'session',
    'api_key',
    'key',
))

BEARER_RE = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9\-_.=]+\b')


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
                out[k] = redact(v, sensitive_keys=sensitive_keys, max_len=max_len)
        return out

    # list/tuple
    if isinstance(value, (list, tuple)):
        return [redact(v, sensitive_keys=sensitive_keys, max_len=max_len) for v in value]

    # other scalars
    return value
