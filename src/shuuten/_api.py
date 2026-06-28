from __future__ import annotations

from contextlib import contextmanager
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


# --- CAPTURE SCOPE / CAPTURE CLASS ---


@contextmanager
def _capture_scope(
    *,
    ctx_obj=None,
    workflow: str | None = None,
    platform: Platform = Platform.AUTO,
    summary: str = 'Automation failed',
    action: str | None = None,
    delivery_mode: DeliveryMode | None = None,
    notifier: Notifier,
    subject_id_getter=None,
    context_getter=None,
    fn_args: tuple = (),
    fn_kwargs: dict | None = None,
    re_raise: bool = True,
):
    fn_kwargs = fn_kwargs or {}
    run_id = str(uuid4())

    rt_token = detect_and_set_context(ctx_obj, platform)
    notify_token = set_notification_context(
        NotificationContext(
            workflow=workflow,
            action=action,
            run_id=run_id,
            delivery_mode=delivery_mode,
        )
    )

    outermost = False

    if delivery_mode is DeliveryMode.DEFERRED:
        if get_deferred_context() is None:
            outermost = True
            deferred_ctx = DeferredContext(
                workflow=workflow,
                action=action,
                run_id=run_id,
                records=[],
            )
            deferred_token = set_deferred_context(deferred_ctx)

    try:
        yield

    except Exception as e:
        subject_id = (
            subject_id_getter(fn_args, fn_kwargs) if subject_id_getter else None
        )
        context = context_getter(fn_args, fn_kwargs) if context_getter else {}
        event = Event(
            level='error',
            summary=summary,
            workflow=workflow,
            action=action,
            subject_id=subject_id,
            context=context,
            run_id=run_id,
        )

        notifier.notify(event, exc=e)

        if re_raise:
            raise

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


class _Capture:
    __slots__ = (
        'notifier',
        'workflow',
        'platform',
        'summary',
        'action',
        'subject_id_getter',
        'context_getter',
        're_raise',
        'context',
        'delivery_mode',
        '_cm',
    )

    def __init__(
        self,
        *,
        config: Config | None = None,
        workflow: str | None = None,
        platform: Platform = Platform.AUTO,
        summary: str = 'Automation failed',
        action: str | None = None,
        delivery_mode: str | DeliveryMode | None = None,
        notifier: Notifier | None = None,
        subject_id_getter=None,
        context_getter=None,
        re_raise: bool = True,
        context=None,
    ):
        init(config)
        self.notifier = notifier or _get_notifier()
        self.workflow = workflow
        self.platform = platform
        self.summary = summary
        self.action = action
        self.subject_id_getter = subject_id_getter
        self.context_getter = context_getter
        self.re_raise = re_raise
        self.context = context
        self._cm = None

        if isinstance(delivery_mode, str):
            self.delivery_mode = DeliveryMode(delivery_mode)
        elif delivery_mode is not None:
            self.delivery_mode = delivery_mode
        else:
            self.delivery_mode = self.notifier.config.delivery_mode

    def _scope(
        self,
        *,
        ctx_obj=None,
        action: str | None = None,
        fn_args: tuple = (),
        fn_kwargs: dict | None = None,
    ):
        return _capture_scope(
            ctx_obj=ctx_obj,
            workflow=self.workflow,
            platform=self.platform,
            summary=self.summary,
            action=action or self.action,
            delivery_mode=self.delivery_mode,
            notifier=self.notifier,
            subject_id_getter=self.subject_id_getter,
            context_getter=self.context_getter,
            fn_args=fn_args,
            fn_kwargs=fn_kwargs,
            re_raise=self.re_raise,
        )

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ctx_obj = args[-1] if args else self.context
            with self._scope(
                ctx_obj=ctx_obj,
                action=self.action or fn.__qualname__,
                fn_args=args,
                fn_kwargs=kwargs,
            ):
                return fn(*args, **kwargs)

        return wrapper

    def __enter__(self):
        self._cm = self._scope(
            ctx_obj=self.context,
            action=self.action or 'capture',
        )
        return self._cm.__enter__()

    def __exit__(self, exc_type, exc, tb):
        if self._cm is None:
            return False
        return self._cm.__exit__(exc_type, exc, tb)


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
    context=None,
):
    """
    Decorator or context manager for AWS Lambda functions,
    ECS tasks, or local code.

    Captures exceptions, enriches them with runtime context, and notifies
    configured destinations. Exceptions are re-raised by default.

    Summary is used only if the wrapped function or context block raises.
    """
    cap = _Capture(
        config=config,
        workflow=workflow,
        platform=platform,
        summary=summary,
        action=action,
        delivery_mode=delivery_mode,
        notifier=notifier,
        subject_id_getter=subject_id_getter,
        context_getter=context_getter,
        re_raise=re_raise,
        context=context,
    )
    return cap(_fn) if _fn else cap


# alias: for people who just want a decorator and don't care about semantics.
wrap = capture
