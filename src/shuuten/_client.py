from __future__ import annotations

from functools import wraps
from logging import (DEBUG,
                     StreamHandler,
                     Logger,
                     getLogger,
                     Handler,
                     Formatter)
from traceback import format_exception
from typing import Iterable

from ._destinations import (SlackWebhookDestination,
                            SESDestination)
from ._integrations import (ShuutenContextFilter,
                            ShuutenJSONFormatter,
                            SlackNotificationHandler)
from ._log import LOG, quiet_third_party_logs
from ._models import Event, Platform, detect_context, ShuutenConfig
from ._redact import redact
from ._runtime import (get_runtime_context,
                       reset_runtime_context,
                       detect_and_set_context)


_NOTIFIER: Notifier | None = None
_HANDLERS: list[Handler] | None = None


def _get_notifier() -> Notifier:
    global _NOTIFIER
    if _NOTIFIER is None:
        init()
    assert _NOTIFIER is not None
    return _NOTIFIER


def notify(
    *,
    level: str,
    summary: str,
    message: str | None = None,
    workflow: str | None = None,
    action: str | None = None,
    subject_id: str | None = None,
    context: dict | None = None,
    exc: BaseException | None = None,
) -> None:
    event = Event(
        level=level,
        summary=summary,
        message=message,
        workflow=workflow,
        action=action,
        subject_id=subject_id,
        context=context or {},
    )
    _get_notifier().notify(event, exc=exc)


def notify_event(event: Event, *, exc: BaseException | None = None) -> None:
    _get_notifier().notify(event, exc=exc)


def setup(config: ShuutenConfig | None = None,
          *,
          formatter: type[Formatter] = ShuutenJSONFormatter,
          reset: bool = False,
          logger_name: str | None = None,
          configure_root: bool = False) -> Logger:

    init(config, formatter=formatter, reset=reset)
    return get_logger(logger_name, configure_root)


def init(config: ShuutenConfig | None = None,
         *,
         formatter: type[Formatter] = ShuutenJSONFormatter,
         reset: bool = False):
    """
    auto-detect destinations via env vars
    """
    global _HANDLERS, _NOTIFIER

    # Skip on Lambda warm start
    if _HANDLERS is not None and not reset:
        return

    config = (ShuutenConfig.from_env()
              if config is None
              else config.with_env_defaults())

    if config.quiet_level is not None:
        quiet_third_party_logs(config.quiet_level)

    ses_from = config.ses_from
    ses_to = config.ses_to

    handler = StreamHandler()
    handler.setFormatter(formatter())
    handler.addFilter(ShuutenContextFilter())

    _HANDLERS = [handler]

    destinations = []
    enable_slack_log_handler = True if config.slack_webhook_url else False

    # DESTINATIONS
    # Slack
    if enable_slack_log_handler:
        LOG.debug('Slack: Found webhook %s',
                  config.slack_webhook_url)
        slack_destination = SlackWebhookDestination(
            webhook_url=config.slack_webhook_url,
            slack_format=config.slack_format,
        )
        destinations.append(slack_destination)
    # Email
    if ses_from and ses_to:
        LOG.debug('SES: Found FROM (%s) and TO (%s)',
                  ses_from, ses_to)
        email_destination = SESDestination(
            from_address=ses_from,
            to_addresses=ses_to,
            reply_to=config.ses_reply_to,
            region_name=config.ses_region,
        )
        destinations.append(email_destination)

    _NOTIFIER = Notifier(
        config,
        destinations=destinations,
    )

    if enable_slack_log_handler:
        slack_handler = SlackNotificationHandler(
            _NOTIFIER,
            min_level=config.min_level
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


def capture(
    workflow: str | None = None,
    platform: Platform = Platform.AUTO,
    summary: str = 'Automation failed',
    action: str | None = None,
    *,
    notifier: Notifier | None = None,
    subject_id_getter=None,  # fn(args, kwargs, result?) -> str | None
    context_getter=None,  # fn(args, kwargs) -> dict
    re_raise: bool = True,
):
    """
    Decorator for AWS Lambda Function or ECS Task or Local.

    Captures exceptions, enriches them with runtime context, and
    notifies configured destinations. Exceptions are re-raised
    by default.
    """
    notifier = notifier or _NOTIFIER

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # detect lambda context safely
            ctx_obj = args[-1] if args else None

            token = detect_and_set_context(ctx_obj, platform)

            try:
                return fn(*args, **kwargs)

            except Exception as e:
                subject_id = subject_id_getter(args, kwargs) if subject_id_getter else None
                context = context_getter(args, kwargs) if context_getter else {}
                event = Event(
                    level='error',
                    summary=summary,
                    workflow=workflow,
                    action=action or fn.__qualname__,
                    subject_id=subject_id,
                    context=context,
                )

                if notifier is not None:
                    notifier.notify(event, exc=e)

                if re_raise:
                    raise

                return None

            finally:
                reset_runtime_context(token)

        return wrapper

    return deco


# alias: for people who just want a decorator and don't care about semantics.
wrap = capture


class Notifier:
    """
    Shuuten notifier.

    The notifier:
        * is a single choke point called by Shuuten
          Handler(s) (ex. SlackNotificationHandler)
        * enriches Event `source` / `log_url` from runtime context
        * sends to pre-configured destinations
          (ex. SlackWebhookDestination)

    """
    __slots__ = (
        '_config',
        '_destinations',
        '_logger',
    )

    def __init__(
        self,
        config: ShuutenConfig,
        *,
        logger: Logger | None = None,
        destinations: Iterable[object] | None = None,
    ):
        self._config = config
        self._destinations = list(destinations) if destinations else []
        self._logger = logger = logger or getLogger(f'{self._config.app}.shuuten')
        logger.propagate = True

    def notify(self, event: Event, *, exc: BaseException | None = None) -> None:
        # fill defaults from config
        if event.env is None:
            event.env = self._config.env

        # enrich source/log_url from runtime context
        # if no context is explicitly set: detect AWS Lambda, ECS, or Local
        rt = get_runtime_context() or detect_context()
        if rt:
            rt.enrich_event_source(event)

        exc_text = None
        if exc is not None:
            exc_text = ''.join(format_exception(type(exc), exc, exc.__traceback__))
            exc_text = redact(exc_text)

        # 1. local log (CloudWatch)
        if self._config.emit_local_log:
            payload = redact({
                'app': self._config.app,
                'level': event.level,
                'summary': event.summary,
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
                    'shuuten_internal': True,  # clear signal for humans / tools
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
