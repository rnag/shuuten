from __future__ import annotations

from functools import wraps
from logging import DEBUG, StreamHandler, Logger, getLogger, Handler, Formatter, ERROR
from os import getenv
from traceback import format_exception
from typing import Iterable

from ._aws_links import cloudwatch_log_stream_link
from ._constants import SLACK_WEBHOOK_ENV_VAR, SLACK_MIN_LVL_ENV_VAR
from ._destinations import SlackWebhookDestination, SLACK_FORMAT_TYPE
from ._integrations import (ShuutenContextFilter,
                            ShuutenJSONFormatter,
                            SlackNotificationHandler)
from ._log import LOG
from ._models import (Event,
                      from_lambda_context)
from ._runtime import get_runtime_context, set_runtime_context, reset_runtime_context
from ._redact import redact


_NOTIFIER: Notifier | None = None
_APP_NAME: str | None = None
_ENV: str | None = None
_HANDLERS: list[Handler] | None = None


def setup(app_name: str,
          *,
          env: str = 'dev',
          min_lvl: str | int = ERROR,
          emit_local_log: bool = True,
          slack_format: SLACK_FORMAT_TYPE = 'blocks',
          logger_name: str | None = None,
          configure_root: bool = False,
          **kwargs) -> Logger:

    init(
        app_name=app_name,
        env=env,
        min_lvl=min_lvl,
        emit_local_log=emit_local_log,
        slack_format=slack_format,
        **kwargs,
    )

    return get_logger(logger_name, configure_root)


def init(app_name: str | None = None,
         env: str | None = 'dev',
         min_lvl: str | int = ERROR,
         emit_local_log: bool = True,
         slack_format: SLACK_FORMAT_TYPE = 'blocks',
         formatter: type[Formatter] = ShuutenJSONFormatter,
         reset: bool = False):
    """
    auto-detect destinations via env vars
    """
    global _APP_NAME, _ENV, _HANDLERS, _NOTIFIER

    # Skip on Lambda warm start
    if _HANDLERS is not None and not reset:
        return

    min_lvl = getenv(SLACK_MIN_LVL_ENV_VAR, min_lvl)

    slack_webhook_url = getenv(SLACK_WEBHOOK_ENV_VAR)

    _APP_NAME = app_name
    _ENV = env

    handler = StreamHandler()
    handler.setFormatter(formatter())
    handler.addFilter(ShuutenContextFilter())

    _HANDLERS = [handler]

    destinations = []
    enable_slack_log_handler = True if slack_webhook_url else False

    if enable_slack_log_handler:
        LOG.debug('Found slack webhook %s', slack_webhook_url)
        slack_destination = SlackWebhookDestination(
            webhook_url=slack_webhook_url,
            slack_format=slack_format,
        )
        destinations.append(slack_destination)

    # TODO: add more destinations

    _NOTIFIER = Notifier(
        app_name=_APP_NAME,
        destinations=destinations,
        enable_local_logging=emit_local_log,
    )

    if enable_slack_log_handler:
        slack_handler = SlackNotificationHandler(
            _NOTIFIER,
            workflow='logs',
            env=_ENV,
            min_level=min_lvl,
        )
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
            # detect lambda context safely
            ctx_obj = args[-1] if args else None

            rt_context = from_lambda_context(ctx_obj, env=env)
            token = set_runtime_context(rt_context)

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

            finally:
                reset_runtime_context(token)

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
        self._destinations = list(destinations) if destinations else []
        self._enable_local_logging = enable_local_logging
        self._logger = logger = logger or getLogger(f'{app_name}.shuuten')
        logger.propagate = True

    def notify(self, event: Event, *, exc: BaseException | None = None) -> None:
        rt = get_runtime_context()

        # Fill event.source / log_url if missing
        if rt and not event.source:
            event.source = {
                'platform': rt.platform,
                'function_name': rt.function_name,
                'request_id': rt.request_id,
                'region': rt.region,
                'log_group': rt.log_group,
                'log_stream': rt.log_stream,
                'cluster': rt.cluster_name,
                'task_arn': rt.task_arn,
            }

        # TODO might move this out
        # for canonical log_url
        if not event.log_url and rt and rt.region and rt.log_group:
            # pick most relevant
            if rt.log_stream:
                event.log_url = cloudwatch_log_stream_link(rt.region, rt.log_group, rt.log_stream)
            else:
                event.log_url = cloudwatch_log_stream_link(rt.region, rt.log_group)

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
            log_fn(
                '[shuuten] notifier emission (local only)',
                extra={
                    'shuuten': payload,
                    'shuuten_internal': True,    # clear signal for humans / tools
                    'shuuten_skip_slack': True,
                },
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
