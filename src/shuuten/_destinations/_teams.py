# src/shuuten/_destinations/_teams.py

from __future__ import annotations

import json

from .._models import Event
from .._requests import send_to_teams

_LEVEL_META = {
    'DEBUG': ('🔎', 'accent', 'emphasis'),
    'INFO': ('ℹ️', 'good', 'good'),
    'WARNING': ('⚠️', 'warning', 'warning'),
    'ERROR': ('🚨', 'attention', 'attention'),
    'CRITICAL': ('🔥', 'attention', 'attention'),
}


def _fact(title: str, value: object | None) -> dict | None:
    if value in (None, ''):
        return None
    return {'title': title, 'value': str(value)}


def _compact_json(value: object, *, limit: int = 1800) -> str:
    text = json.dumps(value, indent=2, default=str, ensure_ascii=False)
    if len(text) > limit:
        return text[:limit] + '\n…[TRUNCATED]'
    return text


def teams_card_for_event(event: Event) -> dict:
    src = event.source or {}
    ctx = event.context or {}

    title = event.summary or event.message or 'Shuuten notification'
    subtitle_parts = [
        event.level.upper() if event.level else None,
        event.env,
        event.workflow,
        event.action,
    ]
    subtitle = ' · '.join(p for p in subtitle_parts if p)

    facts = [
        _fact('App', ctx.get('app')),
        _fact('Env', event.env),
        _fact('Workflow', event.workflow),
        _fact('Action', event.action),
        _fact('Run ID', event.run_id),
        _fact('Subject', event.subject_id),
        _fact('Function', src.get('function_name')),
        _fact('Request ID', src.get('request_id')),
        _fact('Account', src.get('account_name') or src.get('account_id')),
        _fact('Region', src.get('region')),
        _fact('Logger', ctx.get('logger')),
        _fact(
            'File',
            f'{ctx.get("file")}:{ctx.get("lineno")}'
            if ctx.get('file') and ctx.get('lineno')
            else None,
        ),
    ]

    emoji, text_color, container_style = (
        _LEVEL_META.get(event.level.upper(), _LEVEL_META['ERROR'])
    )

    body: list[dict] = [
        {
            'type': 'Container',
            'style': container_style,
            'bleed': True,
            'items': [
                {
                    'type': 'TextBlock',
                    'text': f'{emoji} {title}',
                    'weight': 'Bolder',
                    'size': 'Large',
                    'color': text_color,
                    'wrap': True,
                },
                {
                    'type': 'TextBlock',
                    'text': subtitle,
                    'isSubtle': True,
                    'spacing': 'Small',
                    'wrap': True,
                },
            ],
        },
        {
            'type': 'FactSet',
            'facts': [f for f in facts if f is not None],
        },
    ]

    if event.message:
        body.append(
            {
                'type': 'TextBlock',
                'text': f'**Message**\n\n```\n{event.message[:1800]}\n```',
                'wrap': True,
            }
        )

    context_for_teams = dict(ctx)
    for k in ('app', 'logger', 'file', 'lineno', 'func'):
        context_for_teams.pop(k, None)

    if context_for_teams:
        body.append(
            {
                'type': 'TextBlock',
                'text': '**Details**\n\n```\n'
                f'{_compact_json(context_for_teams)}\n```',
                'wrap': True,
            }
        )

    if event.exception:
        exc = event.exception[-3500:]
        body.append(
            {
                'type': 'TextBlock',
                'text': f'**Exception**\n\n```\n{exc}\n```',
                'wrap': True,
            }
        )

    actions = []
    if event.log_url:
        actions.append(
            {
                'type': 'Action.OpenUrl',
                'title': 'CloudWatch Logs',
                'url': event.log_url,
            }
        )

    if src.get('function_url'):
        actions.append(
            {
                'type': 'Action.OpenUrl',
                'title': 'Lambda',
                'url': src['function_url'],
            }
        )

    if src.get('source_code'):
        actions.append(
            {
                'type': 'Action.OpenUrl',
                'title': 'Source',
                'url': src['source_code'],
            }
        )

    return {
        'type': 'message',
        'attachments': [
            {
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'contentUrl': None,
                'content': {
                    '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
                    'type': 'AdaptiveCard',
                    'version': '1.4',
                    'msTeams': {
                        'width': 'Full',
                    },
                    'body': body,
                    'actions': actions,
                },
            }
        ],
    }


class MSTeamsWebhookDestination:
    __slots__ = ('_webhook_url',)

    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    def send(self, event: Event, *, exc_text: str | None = None) -> None:
        safe = event.safe(exception=exc_text)
        payload = teams_card_for_event(safe)
        send_to_teams(self._webhook_url, payload)
