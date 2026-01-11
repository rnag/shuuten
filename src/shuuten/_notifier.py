from __future__ import annotations

from collections.abc import Iterable
from logging import Logger, getLogger
from traceback import format_exception
from typing import TYPE_CHECKING, Protocol

from ._models import Event, ShuutenConfig, detect_context
from ._redact import redact
from ._runtime import get_runtime_context

if TYPE_CHECKING:
    class SupportsSend(Protocol):
        def send(self, event: Event, *, exc_text: str | None = None) -> None:
            ...


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
        destinations: Iterable[SupportsSend] | None = None,
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
                d.send(event, exc_text=exc_text)
            except Exception:
                # never blow up automation due to notifier failure
                self._logger.debug('Notifier destination failed', exc_info=True)
