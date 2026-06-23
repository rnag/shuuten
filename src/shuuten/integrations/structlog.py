from __future__ import annotations

from hashlib import sha1
from logging import ERROR
from time import time
from typing import TYPE_CHECKING
from uuid import uuid4

from .._api import _get_notifier
from .._log import LOG, level_to_int
from .._models import Event
from .._runtime import get_notification_context

if TYPE_CHECKING:
    from structlog.typing import EventDict, WrappedLogger

# Carry remaining structured fields without duplicating reserved ones.
_STRUCTLOG_META_KEYS = frozenset(
    {
        '_record',
        '_from_structlog',
    }
)
_RESERVED_EVENT_KEYS = (
    frozenset(
        {
            'event',
            'level',
            'logger',
            'filename',
            'lineno',
            'func_name',
            'module',
            'shuuten',
            'data',
            'exc_info',
            'stack_info',
            'shuuten_workflow',
            'shuuten_action',
            'shuuten_subject_id',
        }
    )
    | _STRUCTLOG_META_KEYS
)


def shuuten_processors(*, callsite: bool = True, add_level: bool = True):
    try:
        import structlog
    except ImportError as e:
        raise ImportError(
            "Install structlog support with: pip install 'shuuten[structlog]'"
        ) from e

    processors = []

    if add_level:
        processors.append(structlog.stdlib.add_log_level)

    if callsite:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.MODULE,
                }
            )
        )

    processors.append(ShuutenProcessor())
    return processors


class ShuutenProcessor:
    def __init__(
        self,
        notifier=None,
        *,
        min_level: str | int | None = None,
        workflow: str = 'logs',
        default_summary: str = 'Log forwarded',
        include_stack: bool = True,
        context_getter=None,
        dedupe_window_s: float = 30.0,
    ):
        self._notifier = notifier or _get_notifier()

        # if `min_level` not passed, don't overwrite
        # and use config's `min_level`
        if min_level is None:
            min_level = getattr(self._notifier.config, 'min_level', ERROR)

        self._min_level = level_to_int(min_level)

        self._workflow = workflow
        self._default_summary = default_summary
        self._include_stack = include_stack
        self._context_getter = context_getter
        self._dedupe_window_s = dedupe_window_s
        self._last_sent: dict[str, float] = {}

    def _should_send(self, event_dict: EventDict, level: str, msg: str) -> bool:
        if self._dedupe_window_s <= 0:
            return True

        key_src = (
            f'{level}:'
            f'{event_dict.get("filename", "")}:'
            f'{event_dict.get("lineno", "")}:'
            f'{msg}'
        )
        key = sha1(key_src.encode('utf-8')).hexdigest()

        now = time()
        last = self._last_sent.get(key)

        if last is not None and (now - last) < self._dedupe_window_s:
            return False

        self._last_sent[key] = now
        return True

    def __call__(
        self,
        logger: WrappedLogger,
        name: str,
        event_dict: EventDict,
    ) -> EventDict:

        # name is the structlog method name: "info", "error", "exception", etc.
        level = str(event_dict.get('level') or name).lower()
        level_no = level_to_int(level)

        if level_no < self._min_level:
            return event_dict

        if (
            event_dict.get('shuuten_skip_notify')
            or event_dict.get('shuuten_no_notify')
            or event_dict.get('shuuten_internal')
        ):
            return event_dict

        msg = str(event_dict.get('event', ''))

        if not self._should_send(event_dict, level, msg):
            return event_dict

        try:
            notify_ctx = get_notification_context()

            workflow = (
                event_dict.get('shuuten_workflow')
                or (notify_ctx.workflow if notify_ctx else None)
                or self._workflow
            )

            action = (
                event_dict.get('shuuten_action')
                or (notify_ctx.action if notify_ctx else None)
                or level
            )

            subject_id = event_dict.get('shuuten_subject_id') or (
                notify_ctx.subject_id if notify_ctx else None
            )

            context: dict = {}

            if self._context_getter:
                context.update(self._context_getter(event_dict) or {})

            data_extra = event_dict.get('data')
            if isinstance(data_extra, dict):
                context.update(data_extra)

            shuuten_extra = event_dict.get('shuuten')
            if isinstance(shuuten_extra, dict):
                context['shuuten'] = shuuten_extra

            record = event_dict.get('_record')

            context.update(
                {
                    'logger': getattr(record, 'name', None)
                    or event_dict.get('logger')
                    or event_dict.get('module'),
                    'file': getattr(record, 'filename', None)
                    or event_dict.get('filename'),
                    'lineno': getattr(record, 'lineno', None)
                    or event_dict.get('lineno'),
                    'func': getattr(record, 'funcName', None)
                    or event_dict.get('func_name'),
                    'module': event_dict.get('module'),
                }
            )

            for k, v in event_dict.items():
                if k not in _RESERVED_EVENT_KEYS:
                    context.setdefault(k, v)

            exc = None
            exc_info = event_dict.get('exc_info')
            if isinstance(exc_info, tuple) and len(exc_info) >= 2:
                exc = exc_info[1]
            elif isinstance(exc_info, BaseException):
                exc = exc_info

            if (
                exc is None
                and self._include_stack
                and event_dict.get('stack_info')
            ):
                context['stack'] = event_dict['stack_info']

            event = Event(
                level=level,
                summary=self._default_summary,
                message=msg,
                workflow=workflow,
                action=action,
                subject_id=subject_id,
                run_id=(notify_ctx.run_id if notify_ctx else str(uuid4())),
                env=None,
                context=context,
            )

            self._notifier.notify(event, exc=exc, emit_local_log=False)

        except Exception:
            try:
                LOG.debug(f'{self.__class__.__name__} failed', exc_info=True)
            except Exception:
                pass

        return event_dict
