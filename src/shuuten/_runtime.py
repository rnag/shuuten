from __future__ import annotations

from contextvars import ContextVar, Token

from ._models import RuntimeContext


_runtime_ctx: ContextVar[RuntimeContext | None] = ContextVar(
    'shuuten_runtime_ctx',
    default=None)


def set_runtime_context(ctx: RuntimeContext | None) -> Token:
    return _runtime_ctx.set(ctx)


def reset_runtime_context(token: Token) -> None:
    _runtime_ctx.reset(token)


def get_runtime_context() -> RuntimeContext | None:
    return _runtime_ctx.get()
