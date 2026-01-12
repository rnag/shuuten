from __future__ import annotations

from functools import wraps
from logging import DEBUG, Formatter, Handler, Logger, StreamHandler, getLogger
from typing import cast

from ._destinations import SESDestination, SlackWebhookDestination
from ._integrations import (
    ShuutenContextFilter,
    ShuutenJSONFormatter,
    SlackNotificationHandler,
)
from ._log import LOG, quiet_third_party_logs
from ._models import Config, Event, Platform
from ._notifier import Notifier
from ._runtime import detect_and_set_context, reset_runtime_context

_NOTIFIER: Notifier | None = None
_HANDLERS: list[Handler] | None = None


def _get_notifier() -> Notifier:
    global _NOTIFIER

    if _NOTIFIER is None:
        init()
        if _NOTIFIER is None:
            raise RuntimeError('shuuten.init() did not initialize the notifier')
        return _NOTIFIER

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


def setup(config: Config | None = None,
          *,
          formatter: type[Formatter] = ShuutenJSONFormatter,
          reset: bool = False,
          logger_name: str | None = None,
          configure_root: bool = False) -> Logger:

    init(config, formatter=formatter, reset=reset)
    return get_logger(logger_name, configure_root)


def init(config: Config | None = None,
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

    config = (Config.from_env()
              if config is None
              else config.with_env_defaults())

    if config.quiet_level is not None:
        quiet_third_party_logs(cast(int, config.quiet_level))

    ses_from = config.ses_from
    ses_to = config.ses_to

    handler = StreamHandler()
    handler.setFormatter(formatter())
    handler.addFilter(ShuutenContextFilter())

    _HANDLERS = [handler]

    destinations = []
    slack_url = config.slack_webhook_url

    # DESTINATIONS
    # Slack
    if slack_url is not None:
        LOG.debug('Slack: Found webhook %s',
                  slack_url)
        slack_destination = SlackWebhookDestination(
            webhook_url=slack_url,
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

    if slack_url is not None:
        slack_handler = SlackNotificationHandler(
            _NOTIFIER,
            min_level=config.min_level,
            dedupe_window_s=config.dedupe_window_s,
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
    _fn=None,
    *,
    config: Config | None = None,
    workflow: str | None = None,
    platform: Platform = Platform.AUTO,
    summary: str = 'Automation failed',
    action: str | None = None,
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
    init(config)  # Initialize config (or from env if config=None) if needed
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
                subject_id = (subject_id_getter(args, kwargs)
                              if subject_id_getter else None)
                context = (context_getter(args, kwargs)
                           if context_getter else {})
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

    return deco(_fn) if _fn else deco


# alias: for people who just want a decorator and don't care about semantics.
wrap = capture
