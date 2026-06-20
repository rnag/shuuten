"""Destination webhook utilities for Shuuten."""

import json
import ssl
import urllib.error
import urllib.request
from os import getenv
from typing import Any


def _ssl_context_from_env():
    cafile = getenv('SHUUTEN_CA_BUNDLE') or getenv('SSL_CERT_FILE')
    if cafile:
        ctx = ssl.create_default_context(cafile=cafile)
        return ctx
    return None


def http_get_json(url) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        method='GET',
        headers={'Content-Type': 'application/json'},
    )

    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read().decode('utf-8')

    return json.loads(body)


def send_to_slack(webhook_url: str, payload: dict) -> None:
    send_json_webhook(webhook_url, payload, destination='Slack')


def send_to_teams(webhook_url: str, payload: dict) -> None:
    send_json_webhook(webhook_url, payload, destination='MS Teams')


def send_json_webhook(
    webhook_url: str,
    payload: dict,
    *,
    destination: str = 'webhook',
) -> None:
    """
    Send a message to a `destination` via Incoming Webhook.

    :param webhook_url: Incoming Webhook URL
    :param payload: JSON-serializable message payload
                    (e.g. {"text": "Hello from Shuuten"})
    :param destination: Destination for webhook (ex. 'Slack')
    :raises RuntimeError: if destination returns a non-2xx response
    :raises URLError: if the request fails at the network level
    """
    data = json.dumps(payload).encode('utf-8')

    ctx = _ssl_context_from_env()
    req = urllib.request.Request(
        webhook_url,
        method='POST',
        data=data,
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            r = resp.read()
            if resp.status >= 400:
                body = r.decode('utf-8', errors='replace')
                raise RuntimeError(
                    f'{destination} webhook failed with '
                    f'status {resp.status}: {body}'
                )

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(
            f'{destination} webhook HTTP error {e.code}: {body}'
        ) from e
