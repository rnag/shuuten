from __future__ import annotations

from functools import wraps
from logging import DEBUG, Formatter, Handler, Logger, StreamHandler, getLogger
from uuid import uuid4

from ._log import LOG, quiet_third_party_logs
from ._models import (
    Config,
    DeferredContext,
    DeliveryMode,
    Event,
    NotificationContext,
    Platform,
)
from ._notifier import Notifier
from ._runtime import (
    detect_and_set_context,
    get_deferred_context,
    reset_deferred_context,
    reset_notification_context,
    reset_runtime_context,
    set_deferred_context,
    set_notification_context,
)
from .destinations import (
    MSTeamsWebhookDestination,
    SESDestination,
    SlackWebhookDestination,
)
from .integrations import (
    ShuutenContextFilter,
    ShuutenJSONFormatter,
    ShuutenNotificationHandler,
)

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


def setup(
    config: Config | None = None,
    *,
    formatter: type[Formatter] = ShuutenJSONFormatter,
    reset: bool = False,
    logger_name: str | None = None,
    configure_root: bool = False,
) -> Logger:

    init(config, formatter=formatter, reset=reset)
    return get_logger(logger_name, configure_root)


def init(
    config: Config | None = None,
    *,
    formatter: type[Formatter] = ShuutenJSONFormatter,
    reset: bool = False,
):
    """
    auto-detect destinations via env vars
    """
    global _HANDLERS, _NOTIFIER

    # Skip on Lambda warm start
    if _HANDLERS is not None and not reset:
        return

    config = Config.from_env() if config is None else config.with_env_defaults()

    if config.quiet_level is not None:
        quiet_third_party_logs(config.quiet_level)

    ses_from = config.ses_from
    ses_to = config.ses_to

    handler = StreamHandler()
    handler.setFormatter(formatter())
    handler.addFilter(ShuutenContextFilter())

    _HANDLERS = [handler]

    destinations = []
    slack_url = config.slack_webhook_url
    teams_url = config.teams_webhook_url

    # [DESTINATIONS]
    # Slack
    if slack_url is not None:
        LOG.debug('Slack: Found webhook %s', slack_url)
        slack_destination = SlackWebhookDestination(
            webhook_url=slack_url,
            slack_format=config.slack_format,
        )
        destinations.append(slack_destination)
    # MS Teams
    if teams_url is not None:
        LOG.debug('MS Teams: Found webhook %s', teams_url)
        teams_destination = MSTeamsWebhookDestination(
            webhook_url=teams_url,
        )
        destinations.append(teams_destination)
    # Email
    if ses_from and ses_to:
        LOG.debug('SES: Found FROM (%s) and TO (%s)', ses_from, ses_to)
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

    if destinations:
        notification_handler = ShuutenNotificationHandler(
            _NOTIFIER,
            min_level=config.min_level,
            dedupe_window_s=config.dedupe_window_s,
        )
        # noinspection PyTypeChecker
        _HANDLERS.append(notification_handler)


def get_logger(name: str | None = None, configure_root: bool = False):
    """
    JSON formatter + handler once
    """
    if _HANDLERS is None:
        raise RuntimeError(
            'shuuten.init() must be called before shuuten.get_logger()'
        )

    if name is None and not configure_root:
        raise RuntimeError(
            'Refusing to mutate root logger '
            'formatting until configure_root=True'
        )

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
    delivery_mode: str | DeliveryMode | None = None,
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

    Summary used only if the wrapped function raises.
    """
    # Initialize config (or from env if config=None) if needed.
    # `delivery_mode` is scoped per capture invocation below; it should not
    # mutate global config here.
    init(config)
    notifier = notifier or _NOTIFIER

    effective_delivery_mode = (
        DeliveryMode(delivery_mode)
        if isinstance(delivery_mode, str)
        else delivery_mode
    )

    if effective_delivery_mode is None and notifier is not None:
        effective_delivery_mode = notifier.config.delivery_mode

    def deco(fn):

        @wraps(fn)
        def wrapper(*args, **kwargs):

            # detect lambda context safely
            ctx_obj = args[-1] if args else None
            run_id = str(uuid4())

            rt_token = detect_and_set_context(ctx_obj, platform)
            notify_token = set_notification_context(
                NotificationContext(
                    workflow=workflow,
                    action=action or fn.__qualname__,
                    run_id=run_id,
                    delivery_mode=effective_delivery_mode,
                )
            )

            outermost = False
            # deferred_ctx = None
            # deferred_token = None

            if effective_delivery_mode is DeliveryMode.DEFERRED:
                if get_deferred_context() is None:
                    outermost = True
                    deferred_ctx = DeferredContext(
                        workflow=workflow,
                        action=action or fn.__qualname__,
                        run_id=run_id,
                        records=[],
                    )
                    deferred_token = set_deferred_context(deferred_ctx)

            try:
                return fn(*args, **kwargs)

            except Exception as e:
                subject_id = (
                    subject_id_getter(args, kwargs)
                    if subject_id_getter
                    else None
                )
                context = context_getter(args, kwargs) if context_getter else {}
                event = Event(
                    level='error',
                    summary=summary,
                    workflow=workflow,
                    action=action or fn.__qualname__,
                    subject_id=subject_id,
                    context=context,
                    run_id=run_id,
                )

                if notifier is not None:
                    notifier.notify(event, exc=e)

                if re_raise:
                    raise

                return None

            finally:
                if outermost:
                    # noinspection PyUnboundLocalVariable
                    group_event = deferred_ctx.to_group_event()
                    # noinspection PyProtectedMember
                    notifier._send_now(
                        group_event,
                        exc=None,
                        send_destinations=True,
                    )
                    # noinspection PyUnboundLocalVariable
                    reset_deferred_context(deferred_token)

                reset_notification_context(notify_token)
                reset_runtime_context(rt_token)

        return wrapper

    return deco(_fn) if _fn else deco


# alias: for people who just want a decorator and don't care about semantics.
wrap = capture
