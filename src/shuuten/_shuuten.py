"""Slack webhook utilities for Shuuten."""

import json
import urllib.error
import urllib.request


def send_to_slack(webhook_url: str, payload: dict) -> None:
    """
    Send a message to Slack via Incoming Webhook.

    :param webhook_url: Slack Incoming Webhook URL
    :param payload: JSON-serializable Slack message payload
                    (e.g. {"text": "Hello from Shuuten"})
    :raises RuntimeError: if Slack returns a non-2xx response
    :raises URLError: if the request fails at the network level
    """
    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                body = resp.read().decode('utf-8', errors='replace')
                raise RuntimeError(
                    f'Slack webhook failed with status {resp.status}: {body}'
                )
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(
            f'Slack webhook HTTP error {e.code}: {body}'
        ) from e
