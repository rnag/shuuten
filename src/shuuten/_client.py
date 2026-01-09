from __future__ import annotations

from functools import wraps
from logging import Logger, getLogger
from traceback import format_exception
from typing import Iterable
from ._event import Event
from ._redact import redact


def notify_exceptions(
    notifier,
    *,
    workflow: str,
    env: str,
    title: str = 'Automation failed',
    action: str | None = None,
    subject_id_getter=None,  # fn(args, kwargs, result?) -> str | None
    context_getter=None,     # fn(args, kwargs) -> dict
    re_raise: bool = True,
):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):

            try:
                return fn(*args, **kwargs)

            except Exception as e:
                subject_id = subject_id_getter(args, kwargs) if subject_id_getter else None
                context = context_getter(args, kwargs) if context_getter else {}
                event = Event(
                    level='error',
                    title=title,
                    workflow=workflow,
                    action=action or fn.__qualname__,
                    env=env,
                    subject_id=subject_id,
                    context=context,
                )

                notifier.notify(event, exc=e)

                if re_raise:
                    raise

                return None

        return wrapper

    return deco


class Notifier:

    __slots__ = (
        '_app_name',
        '_logger',
        '_destinations',
        '_enable_local_logging',
    )

    def __init__(
        self,
        *,
        app_name: str,
        logger: Logger | None = None,
        destinations: Iterable[object] | None = None,
        enable_local_logging: bool = True,
    ):
        self._app_name = app_name
        self._logger = logger or getLogger(app_name)
        self._destinations = list(destinations) if destinations else []
        self._enable_local_logging = enable_local_logging

    def notify(self, event: Event, *, exc: BaseException | None = None) -> None:
        exc_text = None
        if exc is not None:
            exc_text = ''.join(format_exception(type(exc), exc, exc.__traceback__))
            exc_text = redact(exc_text)

        # 1. local log (CloudWatch)
        if self._enable_local_logging:
            payload = {
                'app': self._app_name,
                'level': event.level,
                'title': event.title,
                'workflow': event.workflow,
                'action': event.action,
                'env': event.env,
                'run_id': event.run_id,
                'subject_id': event.subject_id,
                'source': event.source,
                'log_url': event.log_url,
                'context': redact(event.context),
            }
            # log as structured dict (formatter can JSON-dump it)
            (getattr(self._logger, event.level) or self._logger.error)(
                event.title,
                extra={'shuuten': payload},
            )

        # 2. Destinations
        for d in self._destinations:
            # noinspection PyBroadException
            try:
                _send = getattr(d, 'send')
                _send(event, exc_text=exc_text)
            except Exception:
                # never blow up automation due to notifier failure
                self._logger.debug('Notifier destination failed', exc_info=True)
