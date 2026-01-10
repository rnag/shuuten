from __future__ import annotations

import os
from logging import DEBUG, StreamHandler, Logger, getLogger, Handler, Formatter, ERROR
from functools import wraps
from traceback import format_exception
from typing import Iterable

from ._constants import SLACK_WEBHOOK_ENV_VAR
from ._event import Event
from ._log import LOG
from ._redact import redact
from ._destinations import SlackWebhookDestination
from ._integrations import (DropNoNotifyFilter,
                            ShuutenJSONFormatter,
                            SlackNotificationHandler)


_NOTIFIER: Notifier | None = None
_APP_NAME: str | None = None
_ENV: str | None = None
_HANDLERS: list[Handler] | None = None


def setup(app_name: str,
          *,
          env: str = 'dev',
          min_lvl: str | int = ERROR,
          enable_slack_log_handler=True,
          logger_name: str | None = None,
          configure_root: bool = False,
          **kwargs) -> Logger:

    init(
        app_name=app_name,
        env=env,
        min_lvl=min_lvl,
        enable_slack_log_handler=enable_slack_log_handler,
        **kwargs,
    )

    return get_logger(logger_name, configure_root)


def init(app_name: str | None = None,
         env: str | None = 'dev',
         formatter: type[Formatter] = ShuutenJSONFormatter,
         min_lvl: str | int = ERROR,
         enable_slack_log_handler=True,
         reset: bool = False):
    """
    auto-detect destinations via env vars
    """
    global _APP_NAME, _ENV, _HANDLERS, _NOTIFIER

    # Skip on Lambda warm start
    if _HANDLERS is not None and not reset:
        return

    _APP_NAME = app_name
    _ENV = env

    _filter = DropNoNotifyFilter()

    handler = StreamHandler()
    handler.addFilter(_filter)
    handler.setFormatter(formatter())

    _HANDLERS = [handler]

    destinations = []
    if hook_url := os.environ.get(SLACK_WEBHOOK_ENV_VAR):
        LOG.debug('Found slack webhook %s', hook_url)
        destinations.append(SlackWebhookDestination(webhook_url=hook_url))

    _NOTIFIER = Notifier(
        app_name=_APP_NAME,
        destinations=destinations
    )

    if enable_slack_log_handler and destinations:
        slack_handler = SlackNotificationHandler(
            _NOTIFIER,
            workflow='logs',
            env=_ENV,
            min_level=min_lvl,
        )
        slack_handler.addFilter(_filter)
        _HANDLERS.append(slack_handler)


def get_logger(name: str | None = None,
               configure_root: bool = False):
    """
    JSON formatter + handler once
    """
    if _HANDLERS is None:
        raise RuntimeError('shuuten.init() must be called '
                           'before shuuten.get_logger()')

    if name is None and not configure_root:
        raise RuntimeError('Refusing to mutate root logger '
                           'formatting until configure_root=True')

    log = getLogger(name)

    for handler in _HANDLERS:
        if handler not in log.handlers:
            log.addHandler(handler)

    log.setLevel(DEBUG)
    log.propagate = False

    return log


def catch(
    workflow: str,
    env: str | None = None,
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

                if _NOTIFIER is not None:
                    _NOTIFIER.notify(event, exc=e)

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
            payload = redact({
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
                'context': event.context,
            })
            # log as structured dict (formatter can JSON-dump it)
            log_fn = getattr(self._logger, event.level, self._logger.error)
            log_fn(event.title, extra={'shuuten': payload, 'shuuten_no_notify': True})

        # 2. Destinations
        for d in self._destinations:
            # noinspection PyBroadException
            try:
                _send = getattr(d, 'send')
                _send(event, exc_text=exc_text)
            except Exception:
                # never blow up automation due to notifier failure
                self._logger.debug('Notifier destination failed', exc_info=True)
