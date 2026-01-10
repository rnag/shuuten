from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from ._models import RuntimeContext, from_lambda_context


_runtime_ctx: ContextVar[RuntimeContext | None] = ContextVar(
    'shuuten_runtime_ctx',
    default=None)


def set_lambda_context(ctx_obj: Any) -> Token:
    rt_context = from_lambda_context(ctx_obj)
    return set_runtime_context(rt_context)


def set_runtime_context(ctx: RuntimeContext | None) -> Token:
    return _runtime_ctx.set(ctx)


def reset_runtime_context(token: Token) -> None:
    _runtime_ctx.reset(token)


def get_runtime_context() -> RuntimeContext | None:
    return _runtime_ctx.get()
