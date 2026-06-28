<div align="center">
<img alt="logo" width="160" src="https://raw.githubusercontent.com/rnag/shuuten/main/img/logo.png">

**Shuuten — last-stop alerts for Python automations**

[![PyPI version](https://img.shields.io/pypi/v/shuuten.svg)](https://pypi.org/project/shuuten)
[![PyPI license](https://img.shields.io/pypi/l/shuuten.svg)](https://pypi.org/project/shuuten)
[![PyPI Python versions](https://img.shields.io/pypi/pyversions/shuuten.svg)](https://pypi.org/project/shuuten)
[![GitHub Actions](https://github.com/rnag/shuuten/actions/workflows/release.yml/badge.svg)](https://github.com/rnag/shuuten/actions/workflows/release.yml)
[![Documentation Status](https://github.com/rnag/shuuten/actions/workflows/gh-pages.yml/badge.svg)](https://shuuten.ritviknag.com)

</div>

<!--intro-start-->

**Stop writing boilerplate alert code.** Shuuten gives your Python automations
structured JSON logging and instant Slack, Microsoft Teams, or email alerts —
with zero dependencies and minimal setup.

Built for AWS Lambda and ECS, works anywhere Python runs.

*終点 (Shūten) — "final stop" in Japanese. The last line of defense before a silent failure.*

## Why Shuuten?

* **Zero dependencies** — no SDKs, agents, or background workers
* **Structured JSON logs** — CloudWatch-friendly out of the box
* **Built for failure paths** — only `ERROR+` alerts are sent by default, no noise
* **Designed for AWS** — Lambda, ECS tasks, and containers work out of the box

## Quick start (AWS Lambda)

```python
import shuuten

@shuuten.capture
def lambda_handler(event, context):
    shuuten.error('domain error')    # → sends alert
    1 / 0                            # → alert with full stack trace
```

Configure one destination:

```bash
# Slack
export SHUUTEN_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
# OR Microsoft Teams
export SHUUTEN_TEAMS_WEBHOOK_URL="https://xxxxx.webhook.office.com/..."
# OR Email (Amazon SES)
export SHUUTEN_SES_FROM="..."
export SHUUTEN_SES_TO="..."
```

That's it.

📖 [Documentation](https://shuuten.ritviknag.com) · ⭐ [Star on GitHub](https://github.com/rnag/shuuten)

## Installation

```bash
pip install shuuten             # core package (logging, Slack, Teams)
pip install "shuuten[email]"    # + SES email support (boto3)
```

## Examples

### Structured logging (logging-style)

> **Note:**
> By default, only `ERROR` and above are sent to configured destinations.
> Lower-severity logs (`DEBUG`, `INFO`, `WARNING`) are emitted locally but are not sent as notifications unless `min_level` is changed.

```python
import shuuten

def handler(event, context):
    shuuten.info('hello')        # not sent
    shuuten.error('bad input')   # sent to configured destinations
```

### Explicit logger + notifications

> Requires SES env vars (`SHUUTEN_SES_FROM`, `SHUUTEN_SES_TO`). Email is sent via AWS SES if configured.

```python
import shuuten

shuuten.init(shuuten.Config(app='my-app', env='dev'))
log = shuuten.get_logger(__name__)


@shuuten.capture(workflow='my-workflow')
def handler(event, context):
    log.error('Something went wrong')  # sent to configured destinations
```

### Deferred delivery

> **Deferred delivery requires `capture()`** (as a decorator or context manager) so
> Shuuten knows when to send grouped notifications.
> It does not catch Lambda hard timeouts or OOM failures.

Use deferred delivery to collect alert-worthy logs during a captured execution
and send one grouped notification at the end.

```python
import shuuten
import logging

shuuten.init(shuuten.Config(min_level=logging.INFO))

log = shuuten.get_logger(__name__)

@shuuten.capture(workflow="orders", delivery_mode="deferred")
def handler(event, context):
    log.info("starting order sync")
    log.error("failed to process order", extra={"data": {"order_id": 123}})
    1 / 0
```

Instead of sending multiple Slack, Teams, or email notifications, Shuuten sends
one grouped notification with the captured logs, context, and exception details.

### Context manager

`capture()` can also be used as a context manager.

```python
import logging
import shuuten

shuuten.init(shuuten.Config(min_level=logging.INFO))

log = shuuten.get_logger(__name__)

with shuuten.capture(workflow="orders", delivery_mode="deferred"):
    log.info("starting order sync")
    log.error("failed to process order", extra={"data": {"order_id": 123}})
    1 / 0
```

### Manual context control (advanced)

```python
import shuuten

def handler(event, context):
    token = shuuten.detect_and_set_context(context)
    try:
        ...
    finally:
        shuuten.reset_runtime_context(token)
```

> `capture()` also works for ECS tasks (via ECS metadata v4).

### Structured logging with `extra`

> Works with both `shuuten.info()` and `log = shuuten.get_logger(__name__)` — any logger using `ShuutenJSONFormatter`.

#### Attach structured context with `data`

Pass a dict under the `data` key in `extra` to merge fields top-level into the
JSON log output:

```python
shuuten.info('Incoming event', extra={
    'data': {
        'method': 'POST',
        'path': '/slack/events',
        'status': 200,
    }
})
# → {"ts": ..., "level": "info", "msg": "Incoming event", "method": "POST", "path": "/slack/events", "status": 200, ...}
```

> **Note:** Keys in `data` must not conflict with shuuten's built-in output
> fields (`ts`, `fn`, `file`, `lineno`, `level`, `msg`, `logger`, `stack`,
> `kind`, `shuuten`, `exc`). A `ValueError` is raised if they do:
> ```
> ValueError: shuuten: extra 'data' keys ['msg'] conflict with built-in log output fields.
> ```

#### Attach internal shuuten context

Use the `shuuten` key to attach structured metadata that is nested under a
`shuuten` field in the output:

```python
shuuten.info('Processing request', extra={'shuuten': {'caller': 'my_fn', 'request_id': '123'}})
# → {"ts": ..., "msg": "Processing request", "shuuten": {"caller": "my_fn", "request_id": "123"}, ...}
```

#### Log a dict or list directly as `msg`

Pass a Python `dict` or `list` directly as the message — it will be embedded
as a native JSON object rather than a stringified representation:

```python
shuuten.info({'event': 'app_requested', 'app_id': 'A123', 'scopes': ['incoming-webhook']})
# → {"ts": ..., "msg": {"event": "app_requested", "app_id": "A123", "scopes": [...]}, ...}
```

This also works with `shuuten.get_logger()`:

```python
log = shuuten.get_logger(__name__)
log.info({'event': 'app_requested', 'app_id': 'A123'})
```

## Integrations

### structlog

[structlog]: https://www.structlog.org/en/stable/

Use Shuuten as a [structlog] processor. Keep `structlog` for logging
and rendering; Shuuten forwards alert-worthy events to configured
destinations.

Requirements:

* Install [structlog] (`pip install shuuten[structlog]`)
* Configure at least one [destination](#supported-destinations)

Then, configure processors for [structlog]:

```python
import logging

import structlog
import shuuten
from shuuten.integrations.structlog import configure_structlog

shuuten.init(
    shuuten.Config(
        min_level=logging.INFO,
        slack_webhook_url="https://hooks.slack.com/services/...",
    )
)

configure_structlog()

log = structlog.get_logger(__name__)

log.debug("logged locally")  # not sent to destinations
log.info("sent because min_level=INFO")
log.error("failed", order_id=123)
```

That's it. Shuuten forwards events at or above `min_level`
to configured destinations while preserving normal structlog
logging and rendering.

> `min_level` controls what Shuuten sends to destinations. It does not filter structlog console output.

## Configuration

> `delivery_mode` can be configured globally via `Config` or
> `SHUUTEN_DELIVERY_MODE`, and overridden per `capture()` invocation.

You can configure Shuuten via `Config` in code **or** environment variables.

| Variable                  | Description                                                   | Default     |
|---------------------------|---------------------------------------------------------------|-------------|
| `SHUUTEN_APP`             | Application name (used for grouping/metadata)                 | auto        |
| `SHUUTEN_ENV`             | Environment name (`prod`, `dev`, `staging`, etc.)             | auto        |
| `SHUUTEN_MIN_LEVEL`       | Minimum level sent to destinations                            | `ERROR`     |
| `SHUUTEN_EMIT_LOCAL_LOG`  | Emit local structured log when notifying                      | `true`      |
| `SHUUTEN_QUIET_LEVEL`     | Silence noisy third-party logs (e.g. boto)                    | `WARNING`   |
| `SHUUTEN_DEDUPE_WINDOW_S` | Notification dedupe window (seconds); `0` disables            | `30`        |
| `SHUUTEN_DELIVERY_MODE`   | Alert delivery mode: `immediate`, `deferred`, or `local_only` | `immediate` |

### Slack

| Variable                    | Description                |
|-----------------------------|----------------------------|
| `SHUUTEN_SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `SHUUTEN_SLACK_FORMAT`      | `blocks` or `plain`        |

See [Slack webhook setup](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)

### Microsoft Teams

| Variable                    | Description                          |
|-----------------------------|--------------------------------------|
| `SHUUTEN_TEAMS_WEBHOOK_URL` | Microsoft Teams Incoming Webhook URL |

See [Microsoft Teams Webhook Setup](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)

### Email (SES)

| Variable               | Description                    |
|------------------------|--------------------------------|
| `SHUUTEN_SES_FROM`     | Verified SES sender            |
| `SHUUTEN_SES_TO`       | Comma-separated recipient list |
| `SHUUTEN_SES_REPLY_TO` | Optional reply-to address      |
| `SHUUTEN_SES_REGION`   | Optional SES region            |

## Supported destinations

* **Slack** ([Incoming Webhooks](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/))
* **Microsoft Teams** ([Incoming Webhooks](https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook))
* **Email** (AWS SES)
  > Note: When running in AWS (e.g. Lambda or ECS), the execution role must be allowed to send email via SES.
  See [AWS docs](https://docs.aws.amazon.com/pinpoint/latest/developerguide/permissions-ses.html).

## Roadmap

* AWS Lambda failure monitoring
* PagerDuty and JSM destinations
* Expanded ECS and EKS support

## Credits

Created with Cookiecutter using
[https://github.com/audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage)

<!--intro-end-->
