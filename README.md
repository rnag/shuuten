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

**Stop writing boilerplate alert code.** Shuuten gives your Python automations structured JSON logging and instant Slack (or email) alerts when things go wrong — with zero dependencies and minimal setup.

Built for AWS Lambda and ECS, works anywhere Python runs.

*終点 (Shūten) — "final stop" in Japanese. The last line of defense before a silent failure.*

📖 [Documentation](https://shuuten.ritviknag.com) · ⭐ [Star on GitHub](https://github.com/rnag/shuuten)

## Why Shuuten?

* **Zero dependencies** — no SDKs, agents, or background workers
* **3 lines to set up** — decorator + one env var and you're done
* **Structured JSON logs** — CloudWatch-friendly out of the box
* **Built for failure paths** — only `ERROR+` alerts are sent by default, no noise
* **Designed for AWS** — Lambda, ECS tasks, and containers work out of the box
* **Logging-native** — uses familiar `logging` semantics, no new concepts

## Quick start (AWS Lambda)

```python
import shuuten

@shuuten.capture
def lambda_handler(event, context):
    shuuten.debug('debug info')      # logged locally, not sent
    shuuten.error('domain error')    # → Slack
    1 / 0                            # → Slack with full stack trace
```

One environment variable (see [Slack webhook setup](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)):

```bash
export SHUUTEN_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

That's it.

## Installation

```bash
pip install shuuten             # no dependencies (Slack, local logging)
pip install "shuuten[email]"    # SES email (boto3) outside AWS Lambda
```

## Usage patterns

### Structured logging (logging-style)

```python
import shuuten

def handler(event, context):
    shuuten.info('hello')        # not sent
    shuuten.error('bad input')   # sent to Slack if configured
```

### Explicit logger + email notifications

> Requires SES env vars (`SHUUTEN_SES_FROM`, `SHUUTEN_SES_TO`). Email is sent via AWS SES if configured.

```python
import shuuten

shuuten.init(shuuten.Config(app='my-app', env='dev'))
log = shuuten.get_logger(__name__)


@shuuten.capture(workflow='my-workflow')
def handler(event, context):
    log.critical('Something went wrong')  # sent to Slack + Email (if configured)
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

> The `capture()` decorator works for ECS tasks as well (via ECS metadata v4).

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

## Configuration

You can configure Shuuten via `Config` in code **or** environment variables.

| Variable                  | Description                                       | Default   |
|---------------------------|---------------------------------------------------|-----------|
| `SHUUTEN_APP`             | Application name (used for grouping/metadata)     | auto      |
| `SHUUTEN_ENV`             | Environment name (`prod`, `dev`, `staging`, etc.) | auto      |
| `SHUUTEN_MIN_LEVEL`       | Minimum level sent to destinations                | `ERROR`   |
| `SHUUTEN_EMIT_LOCAL_LOG`  | Emit local structured log when notifying          | `true`    |
| `SHUUTEN_QUIET_LEVEL`     | Silence noisy third-party logs (e.g. boto)        | `WARNING` |
| `SHUUTEN_DEDUPE_WINDOW_S` | Slack dedupe window (seconds); `0` disables       | `30`      |

### Slack

| Variable                    | Description                |
|-----------------------------|----------------------------|
| `SHUUTEN_SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `SHUUTEN_SLACK_FORMAT`      | `blocks` or `plain`        |

### Microsoft Teams

| Variable                    | Description                   |
|-----------------------------|-------------------------------|
| `SHUUTEN_TEAMS_WEBHOOK_URL` | MS Teams Incoming Webhook URL |

### Email (SES)

| Variable               | Description                    |
|------------------------|--------------------------------|
| `SHUUTEN_SES_FROM`     | Verified SES sender            |
| `SHUUTEN_SES_TO`       | Comma-separated recipient list |
| `SHUUTEN_SES_REPLY_TO` | Optional reply-to address      |
| `SHUUTEN_SES_REGION`   | Optional SES region            |

## Supported destinations

* **MS Teams** (Incoming Webhooks)
* **Slack** (Incoming Webhooks)
* **Email** (AWS SES)
  > Note: When running in AWS (e.g. Lambda or ECS), the execution role must be allowed to send email via SES.
  See [AWS docs](https://docs.aws.amazon.com/pinpoint/latest/developerguide/permissions-ses.html).

## Roadmap

* MS Teams webhook destination
* Structlog processor integration
* PagerDuty / JSM Alerting destination
* Context manager for exception capture
* Optional "exceptions-only" alerting mode
* Expanded ECS and EKS support

## Credits

Created with Cookiecutter using
[https://github.com/audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage)

<!--intro-end-->
