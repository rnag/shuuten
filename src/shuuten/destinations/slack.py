from __future__ import annotations

import json

from .._formatting import (
    alert_details,
    format_alert_location,
    get_group_alerts,
    is_grouped_event,
)
from .._models import Event, SlackFormat
from .._requests import send_to_slack

_LEVEL_EMOJI = {
    'DEBUG': '🔎',
    'INFO': 'ℹ️',
    'WARNING': '⚠️',
    'ERROR': '🚨',
    'CRITICAL': '🔥',
}


def _field(label: str, value: object | None) -> dict | None:
    if value in (None, ''):
        return None
    return {'type': 'mrkdwn', 'text': f'*{label}*\n{value}'}


def _code_block(
    title: str,
    text: str,
    *,
    limit: int = 1800,
) -> dict:
    if len(text) > limit:
        text = text[:limit] + '\n…[TRUNCATED]'

    return {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': f'*{title}*\n```{text}```',
        },
    }


def _json_block(
    title: str,
    value: dict,
    *,
    limit: int = 1500,
) -> dict:
    text = json.dumps(
        value,
        indent=2,
        default=str,
        ensure_ascii=False,
    )

    if len(text) > limit:
        text = text[:limit] + '\n…[TRUNCATED]'

    return _code_block(title, text, limit=10_000)


def _header(event: Event, *, show_level: bool = True) -> list[dict]:
    lvl = event.level.upper()
    emoji = _LEVEL_EMOJI.get(lvl, '🚨')
    title = event.summary or event.message or 'Shuuten alert'

    if show_level:
        text = f'{emoji} {lvl}: {title}'
    else:
        text = f'{emoji} {title}'

    return [
        {
            'type': 'header',
            'text': {'type': 'plain_text', 'text': text[:150], 'emoji': True},
        }
    ]


def _meta_fields(event: Event) -> list[dict]:
    src = event.source or {}
    ctx = event.context or {}

    fields = [
        _field('App', ctx.get('app')),
        _field('Env', event.env),
        _field('Workflow', event.workflow),
        _field('Action', event.action),
        _field('Run ID', event.run_id),
        _field('Function', src.get('function_name')),
        _field('Request ID', src.get('request_id')),
        _field('Account', src.get('account_name') or src.get('account_id')),
        _field('Region', src.get('region')),
        _field('Logger', ctx.get('logger')),
        _field(
            'File',
            f'{ctx.get("file")}:{ctx.get("lineno")}'
            if ctx.get('file') and ctx.get('lineno')
            else None,
        ),
    ]

    return [f for f in fields if f is not None]


def _links(event: Event) -> list[dict]:
    src = event.source or {}
    links = []

    if event.log_url:
        links.append(f'<{event.log_url}|CloudWatch Logs>')
    if src.get('function_url'):
        links.append(f'<{src["function_url"]}|Lambda>')
    if src.get('source_code'):
        links.append(f'<{src["source_code"]}|Source>')

    if not links:
        return []

    return [
        {
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': ' · '.join(links)},
        }
    ]


def _visible_context(
    ctx: dict,
    *,
    drop_alerts: bool = False,
) -> dict:
    out = dict(ctx)

    for k in ('app', 'logger', 'file', 'lineno', 'func'):
        out.pop(k, None)

    if drop_alerts:
        out.pop('alerts', None)

    return out


def slack_blocks_for_event(event: Event) -> list[dict]:
    if is_grouped_event(event):
        return slack_blocks_for_grouped_event(event)
    return slack_blocks_for_single_event(event)


def slack_blocks_for_grouped_event(event: Event) -> list[dict]:
    blocks = _header(event, show_level=False)

    fields = _meta_fields(event)
    if fields:
        blocks.append({'type': 'section', 'fields': fields[:10]})

    blocks.extend(_links(event))

    alerts = get_group_alerts(event)
    if alerts:
        lines = []

        for i, alert in enumerate(alerts[:10], start=1):
            level = str(alert.get('level', '')).upper()
            msg = alert.get('message') or alert.get('summary') or 'Alert'
            exception = alert.get('exception')

            loc = format_alert_location(alert)
            details = alert_details(alert)

            emoji = _LEVEL_EMOJI.get(level, '•')
            lines.append(f'{i}. {emoji} *{level}*')
            if loc:
                lines.append(f'   `{loc}`')

            # title = format_alert_title(alert)
            if exception:
                lines.append(f'   `{exception}`')
            else:
                lines.append(f'   *Message*```{msg}```')

            if details and isinstance(details, dict):
                lines.append(
                    '   *Context*```'
                    + json.dumps(
                        details,
                        indent=2,
                        default=str,
                        ensure_ascii=False,
                    )[:800]
                    + '```'
                )

            if traceback_text := alert.get('traceback'):
                lines.append(f'```{str(traceback_text)[-1800:]}```')

        if len(alerts) > 10:
            lines.append(f'… {len(alerts) - 10} more alerts')

        blocks.append(
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': '*Alerts captured*\n\n' + '\n\n'.join(lines),
                },
            }
        )

    ctx = _visible_context(event.context or {}, drop_alerts=True)
    if ctx:
        blocks.append(_json_block('Details', ctx))

    blocks.append({'type': 'divider'})
    return blocks


def slack_blocks_for_single_event(event: Event) -> list[dict]:
    blocks = _header(event, show_level=True)

    fields = _meta_fields(event)
    if fields:
        blocks.append({'type': 'section', 'fields': fields[:10]})

    blocks.extend(_links(event))

    if event.message and not event.exception:
        blocks.append(_code_block('Message', event.message, limit=1800))

    if event.exception:
        blocks.append(_code_block('Exception', event.exception[-2500:]))

    ctx = _visible_context(event.context or {})
    if ctx:
        blocks.append(_json_block('Details', ctx))

    blocks.append({'type': 'divider'})
    return blocks


class SlackWebhookDestination:
    __slots__ = (
        '_webhook_url',
        '_username',
        '_slack_format',
    )

    def __init__(
        self,
        webhook_url: str,
        slack_format: SlackFormat = SlackFormat.BLOCKS,
        *,
        username: str | None = None,
    ):

        self._webhook_url = webhook_url
        self._username = username
        self._slack_format = slack_format

    def send(self, event: Event, *, exc_text: str | None = None) -> None:
        safe = event.safe(exception=exc_text)

        if self._slack_format is SlackFormat.BLOCKS:
            fallback = safe.message or safe.summary or 'Shuuten Notification'
            # Slack block kit (default)
            payload = {
                # fallback for notifications/search
                'text': f'{safe.level}: {fallback} ({safe.env})',
                'blocks': slack_blocks_for_event(safe),
            }
        else:
            ctx = safe.context or {}
            app = ctx.get('app')
            # Simple text payload
            text = (
                f'🚨 *{safe.summary}*\n'
                + (f'*app*: {app} | ' if app else '')
                + f'*env*: {safe.env} | '
                f'*workflow*: {safe.workflow} | '
                f'*action*: {safe.action}\n'
                f'*run_id*: {safe.run_id}\n'
            )

            if safe.subject_id:
                text += f'*subject*: {safe.subject_id}\n'
            if safe.log_url:
                text += f'*logs*: {safe.log_url}\n'
            if safe.exception:
                text += f'```{safe.exception}```'
            if safe.message:
                text += f'*msg*: ```{safe.message}```'

            payload = {'text': text}

        if self._username:
            payload['username'] = self._username

        return send_to_slack(self._webhook_url, payload)
