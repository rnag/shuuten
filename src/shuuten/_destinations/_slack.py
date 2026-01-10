from __future__ import annotations

import json
import urllib.request

from typing import Optional
from .._event import Event
from .._redact import redact


class SlackWebhookDestination:
    def __init__(
            self,
            webhook_url: str,
            *,
            username: str | None = None):

        self.webhook_url = webhook_url
        self.username = username

    def send(self, event: Event, *, exc_text: Optional[str] = None) -> None:
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

        # simple text payload (Block Kit later)
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
        if self.username:
            payload['username'] = self.username

        req = urllib.request.Request(
            self.webhook_url,
            method='POST',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
