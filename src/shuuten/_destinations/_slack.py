from __future__ import annotations

import json
from typing import Literal

from .._models import Event
from .._requests import send_to_slack


SLACK_FORMAT_TYPE = Literal['blocks', 'plain']


def slack_blocks_for_event(event: Event) -> list[dict]:
    src = event.source or {}
    ctx = event.context or {}

    exc_text = event.exception

    def add_field(fields: list[dict], label: str, value: str | None):
        if value:
            fields.append({'type': 'mrkdwn', 'text': f'*{label}*\n{value}'})

    # Header: plain_text only
    if exc_text:
        header_text = f"🚨 {event.summary}"
        top_line = f"*{event.level}* — `{event.action}`"
    else:
        # for forwarded logs: show actual message in a visible way
        header_text = f"{event.level}: {(event.message or event.summary or 'Log')}"
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
    if (not exc_text) and event.message:
        blocks.append({
            'type': 'section',
            'text': {'type': 'mrkdwn',
                     'text': f"*Message*\n```{event.message[:1800]}```"},
        })

    # Key fields (keep compact)
    f: list[dict] = []
    add_field(f, 'Env', event.env)
    add_field(f, 'Workflow', event.workflow)
    add_field(f, 'Run ID', event.run_id)
    add_field(f, 'Function', src.get('function_name'))
    add_field(f, 'Request ID', src.get('request_id'))
    add_field(f, 'Account', src.get('account_name') or src.get('account_id'))
    add_field(f, 'Region', src.get('region'))

    # Optional call-site fields (if you include them)
    add_field(f, 'Logger', ctx.get('logger'))
    add_field(f, 'File',
              f"{ctx.get('file')}:{ctx.get('lineno')}"
              if ctx.get('file') and ctx.get('lineno') else None)

    if f:
        blocks.append({'type': 'section', 'fields': f[:10]})

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

    # Context: don’t repeat logger/file/etc (it’s already shown)
    context_for_slack = dict(ctx)
    for k in ('logger', 'file', 'lineno', 'func'):
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
        # event.exception should already be set (or set it here)
        if exc_text and not event.exception:
            event.exception = exc_text

        safe = event.safe()

        if self._slack_format == 'blocks':
            fallback = safe.message or safe.summary or 'Shuuten Notification'
            # Slack block kit (default)
            payload = {
                'text': f'{safe.level}: {fallback} ({safe.env})',  # fallback for notifications/search
                'blocks': slack_blocks_for_event(safe)
            }
        else:
            # Simple text payload
            text = (
                f"🚨 *{safe.summary}*\n"
                f"*env*: {safe.env} | *workflow*: {safe.workflow} | *action*: {safe.action}\n"
                f"*run_id*: {safe.run_id}\n"
            )
            if safe.subject_id:
                text += f"*subject*: {safe.subject_id}\n"
            if safe.log_url:
                text += f"*logs*: {safe.log_url}\n"
            if safe.exception:
                text += f"```{safe.exception}```"
            if safe.message:
                text += f"*msg*: ```{safe.message}```"

            payload = {'text': text}

        if self._username:
            payload['username'] = self._username

        return send_to_slack(self._webhook_url, payload)
