from __future__ import annotations

import logging
from hashlib import sha1
from json import dumps
from logging import ERROR, Formatter, Handler, LogRecord
from time import time

from .._aws_links import cloudwatch_log_stream_link
from .._log import LOG
from .._models import Event
from .._redact import redact
from .._runtime import get_runtime_context


class DropInternalSlackNotifyFilter(logging.Filter):
    """
    Filter that drops records with `shuuten_no_notify`
    """
    def filter(self, record: logging.LogRecord) -> bool:
        return not getattr(record, 'shuuten_skip_slack', False)


class ShuutenContextFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        # Attach for formatters/handlers
        # TODO if no context is explicitly set:
        #   detect Lambda by AWS_LAMBDA_FUNCTION_NAME
        #   detect ECS by ECS_CONTAINER_METADATA_URI_V4
        #       else local
        record.shuuten_rt = get_runtime_context()
        return True


class SlackNotificationHandler(Handler):
    """
    Forwards ERROR+ log records to the global Shuuten notifier (or a passed-in notifier).

    Intended for "oops" paths; keep level high (ERROR/CRITICAL) to avoid spam.
    """

    def __init__(
        self,
        notifier,  # Notifier
        *,
        workflow: str,
        env: str | None = None,
        min_level: str | int = ERROR,
        title: str = 'Automation error',
        include_stack: bool = True,
        context_getter=None,  # fn(record) -> dict
        dedupe_window_s: float = 30.0,
    ):
        if isinstance(min_level, str):
            # noinspection PyUnresolvedReferences,PyProtectedMember
            min_level = logging._nameToLevel.get(min_level.upper(), ERROR)

        super().__init__(level=min_level)  # logging will filter by level for us
        self._notifier = notifier
        self._workflow = workflow
        self._env = env
        self._title = title
        self._include_stack = include_stack
        self._context_getter = context_getter
        self._dedupe_window_s = dedupe_window_s
        self._last_sent: dict[str, float] = {}

        # filter to drop records with `shuuten_no_notify`
        self.addFilter(DropInternalSlackNotifyFilter())
        # context filter so `shuuten_rt` is present in each log record
        self.addFilter(ShuutenContextFilter())

    def _should_send(self, record: LogRecord, msg: str) -> bool:
        # Dedupe by message + call-site
        key_src = f'{record.name}:{record.filename}:{record.lineno}:{msg}'
        key = sha1(key_src.encode('utf-8')).hexdigest()
        now = time()
        last = self._last_sent.get(key)
        if last is not None and (now - last) < self._dedupe_window_s:
            return False
        self._last_sent[key] = now
        return True

    def emit(self, record: LogRecord) -> None:
        # record.getMessage() formats %s args
        msg = record.getMessage()
        if not self._should_send(record, msg):
            return

        # noinspection PyBroadException
        try:
            context: dict = {}
            if self._context_getter:
                context = self._context_getter(record) or {}

            # carry through any structured extra the user attached
            shuuten_extra = getattr(record, 'shuuten', None)
            if isinstance(shuuten_extra, dict):
                context |= {'shuuten': shuuten_extra}

            # Add call-site info (helpful in Slack)
            context.update({
                'logger': record.name,
                'file': record.filename,
                'lineno': record.lineno,
                'func': record.funcName,
                'msg': msg,
            })

            level = record.levelname.lower()
            action = record.name  # Prefer logger name as 'action'

            if record.exc_info:
                exc = record.exc_info[1]
                title = self._title
            else:
                exc = None
                title = 'Log forwarded'

            event = Event(
                level=level,
                title=title,
                workflow=self._workflow,
                action=action,
                env=self._env,
                context=redact(context),
            )

            if exc is None and self._include_stack and record.stack_info:
                # treat stack_info as part of context
                event.context['stack'] = redact(record.stack_info)

            # Attach runtime context + links if available
            rt = getattr(record, 'shuuten_rt', None)

            # If we have a RuntimeContext, enrich source/log_url here
            if rt:
                # TODO seems expensive to run this each time

                event.source = {
                    'platform': rt.platform,
                    'function_name': rt.function_name,
                    'request_id': rt.request_id,
                    'region': rt.region,
                    'log_group': rt.log_group,
                    'log_stream': rt.log_stream,
                    'cluster': rt.cluster_name,
                    'task_arn': rt.task_arn,
                    # optional extras
                    # 'account_id': getattr(rt, 'account_id', None),
                    'account_name': getattr(rt, 'account_name', None),
                    'source_code': getattr(rt, 'source_code', None),
                }

                # If we have an AWS link builder, set event.log_url
                if rt.region and rt.log_group and not event.log_url:
                    event.log_url = cloudwatch_log_stream_link(
                        rt.region, rt.log_group, rt.log_stream
                    )

            self._notifier.notify(event, exc=exc)

        except Exception:
            # never raise from logging handler
            # noinspection PyBroadException
            try:
                LOG.debug(
                    f'{self.__class__.__name__} failed', exc_info=True
                )
            except Exception:
                pass


class ShuutenJSONFormatter(Formatter):

    def format(self, record: LogRecord) -> str:
        base = {
            'ts': record.created,
            'fn': record.funcName,
            'file': record.filename,
            'lineno': record.lineno,
            'level': record.levelname.lower(),
            'msg': record.getMessage(),
            'logger': record.name,
        }
        if record.stack_info:
            base['stack'] = record.stack_info
        if getattr(record, 'shuuten_internal', False):
            base['kind'] = 'shuuten.signal'

        extra = getattr(record, 'shuuten', None)
        if extra:
            base['shuuten'] = extra
        if record.exc_info:
            base['exc'] = self.formatException(record.exc_info)

        return dumps(base, ensure_ascii=False)
