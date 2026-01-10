from __future__ import annotations

import json
import urllib.request

from typing import Literal
from .._models import Event
from .._redact import redact


SLACK_FORMAT_TYPE = Literal['blocks', 'plain']


def _event_message(event: Event) -> str | None:
    ctx = event.context or {}
    msg = ctx.get('msg')
    if isinstance(msg, str) and msg.strip():
        return msg.strip()
    # fallback: sometimes users may put "message" or "error"
    for k in ('message', 'error', 'detail'):
        v = ctx.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def slack_blocks_for_event(event: Event, exc_text: str | None) -> list[dict]:
    src = event.source or {}
    ctx = event.context or {}

    def add_field(fields: list[dict], label: str, value: str | None):
        if value:
            fields.append({'type': 'mrkdwn', 'text': f'*{label}*\n{value}'})

    msg = _event_message(event)

    # Header: plain_text only
    if exc_text:
        header_text = f"🚨 {event.title}"
        top_line = f"*{event.level.upper()}* — `{event.action}`"
    else:
        # for forwarded logs: show actual message in a visible way
        lvl = event.level.upper()
        header_text = f"{lvl}: {(msg or event.title or 'Log')}"
        top_line = f"`{event.action}`"

    blocks: list[dict] = [
        {
            'type': 'header',
            'text': {'type': 'plain_text', 'text': header_text[:150], 'emoji': True},
        },
        {
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': top_line},
        },
    ]

    # Put message in its own section (mrkdwn supports backticks)
    if (not exc_text) and msg:
        blocks.append({
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': f"*Message*\n```{msg[:1800]}```"},
        })

    # Key fields (keep compact)
    fields: list[dict] = []
    add_field(fields, 'Env', event.env)
    add_field(fields, 'Workflow', event.workflow)
    add_field(fields, 'Run ID', event.run_id)
    add_field(fields, 'Function', src.get('function_name'))
    add_field(fields, 'Request ID', src.get('request_id'))
    add_field(fields, 'Account', src.get('account_name') or src.get('account_id'))
    add_field(fields, 'Region', src.get('region'))

    # Optional callsite fields (if you include them)
    add_field(fields, 'Logger', ctx.get('logger'))
    add_field(fields, 'File', f"{ctx.get('file')}:{ctx.get('lineno')}" if ctx.get('file') and ctx.get('lineno') else None)

    if fields:
        blocks.append({'type': 'section', 'fields': fields[:10]})

    # Links row
    links = []
    if event.log_url:
        links.append(f'<{event.log_url}|CloudWatch Logs>')
    fn_url = src.get('function_url')
    if fn_url:
        links.append(f'<{fn_url}|Lambda>')
    repo = src.get('source_code')
    if repo:
        links.append(f'<{repo}|Source>')

    if links:
        blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': ' · '.join(links)}})

    # Exception (only when present)
    if exc_text:
        trimmed = exc_text[-2500:]
        blocks.append({
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': f'*Exception*\n```{trimmed}```'},
        })

    # Context: don’t repeat msg/logger/file/etc (it’s already shown)
    context_for_slack = dict(ctx)
    for k in ('msg', 'logger', 'file', 'lineno', 'func'):
        context_for_slack.pop(k, None)

    if context_for_slack:
        ctx_json = json.dumps(context_for_slack, indent=2, default=str)
        ctx_json = ctx_json[:1500]
        blocks.append({
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': f'*Details*\n```{ctx_json}```'},
        })

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
            slack_format: SLACK_FORMAT_TYPE = 'blocks',
            *,
            username: str | None = None):

        self._webhook_url = webhook_url
        self._username = username
        self._slack_format = slack_format

    def send(self, event: Event, *, exc_text: str | None = None) -> None:
        safe = redact({
            'title': event.title,
            'level': event.level,
            'workflow': event.workflow,
            'action': event.action,
            'env': event.env,
            'run_id': event.run_id,
            'subject_id': event.subject_id,
            'source': event.source,
            'log_url': event.log_url,
            'context': event.context,
            'exception': exc_text,
        })

        if self._slack_format == 'blocks':
            msg = _event_message(event)
            fallback = msg or event.title or 'Shuuten Notification'
            # Slack block kit (default)
            payload = {
                'text': f'{event.level.upper()}: {fallback} ({event.env})',  # fallback for notifications/search
                'blocks': slack_blocks_for_event(event, exc_text)
            }
        else:
            # Simple text payload
            text = (
                f"🚨 *{safe['title']}*\n"
                f"*env*: {safe['env']} | *workflow*: {safe['workflow']} | *action*: {safe['action']}\n"
                f"*run_id*: {safe['run_id']}\n"
            )
            if safe.get('subject_id'):
                text += f"*subject*: {safe['subject_id']}\n"
            if safe.get('log_url'):
                text += f"*logs*: {safe['log_url']}\n"
            if safe.get('exception'):
                text += f"```{safe['exception']}```"
            if 'msg' in safe['context']:
                text += f"*msg*: ```{safe['context']['msg']}```"

            payload = {'text': text}

        if self._username:
            payload['username'] = self._username

        req = urllib.request.Request(
            self._webhook_url,
            method='POST',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
