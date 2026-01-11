<div align="center">
<img alt="logo" width="160" src="https://raw.githubusercontent.com/rnag/shuuten/main/img/logo.png">

**Shuuten Signal — last-stop signals for automation failures**

[![PyPI version](https://img.shields.io/pypi/v/shuuten.svg)](https://pypi.org/project/shuuten)
[![PyPI license](https://img.shields.io/pypi/l/shuuten.svg)](https://pypi.org/project/shuuten)
[![PyPI Python versions](https://img.shields.io/pypi/pyversions/shuuten.svg)](https://pypi.org/project/shuuten)
[![GitHub Actions](https://github.com/rnag/shuuten/actions/workflows/release.yml/badge.svg)](https://github.com/rnag/shuuten/actions/workflows/release.yml)
[![Documentation Status](https://github.com/rnag/shuuten/actions/workflows/gh-pages.yml/badge.svg)](https://shuuten.ritviknag.com)

</div>

<!--intro-start-->

**Shuuten sends structured Slack and email alerts** when your Python automations fail — especially in AWS Lambda and ECS — with minimal setup and zero dependencies.

*終点 (Shūten) means "final stop" in Japanese — the point where a workflow ends and signals that something needs attention.*

📖 [Documentation](https://shuuten.ritviknag.com) · ⭐ [Star on GitHub](https://github.com/rnag/shuuten)

### Quick start (AWS Lambda)

```python
import shuuten

@shuuten.capture
def lambda_handler(event, context):
    shuuten.debug('debug info')      # not sent
    shuuten.error('domain error')    # sent to Slack
    1 / 0                            # sent with stack trace
```

Set one environment variable and you’re done
(see [Slack webhook setup](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)):

```bash
export SHUUTEN_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

## Why Shuuten?

* **Built for failure paths** — only `ERROR+` signals are sent by default
* **Zero dependencies** — no SDKs, agents, or background workers
* **Designed for AWS** — Lambda, ECS tasks, and containers work out of the box
* **Logging-native** — uses familiar `logging` semantics
* **Opinionated but minimal** — small surface area, easy to reason about

## Installation

```bash
pip install shuuten
```

## Usage patterns

### Structured logging (logging-style)

```python
import shuuten

def handler(event, context):
    shuuten.info('hello')        # not sent
    shuuten.error('bad input')   # sent to Slack
```

### Explicit logger + email notifications

```python
import shuuten

shuuten.init(shuuten.ShuutenConfig(app='my-app', env='dev'))
log = shuuten.get_logger(__name__)

@shuuten.capture(workflow='my-workflow')
def handler(event, context):
    log.critical('Something went wrong')  # sent to Slack + Email
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

## Configuration

You can configure Shuuten via `ShuutenConfig` in code **or** environment variables.

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

### Email (SES)

| Variable               | Description                    |
|------------------------|--------------------------------|
| `SHUUTEN_SES_FROM`     | Verified SES sender            |
| `SHUUTEN_SES_TO`       | Comma-separated recipient list |
| `SHUUTEN_SES_REPLY_TO` | Optional reply-to address      |
| `SHUUTEN_SES_REGION`   | Optional SES region            |

## Supported destinations

* **Slack** (Incoming Webhooks)
* **Email** (AWS SES)

## Roadmap

* PagerDuty and other alerting destinations
* Context manager for exception capture
* Optional "exceptions-only" alerting mode
* Expanded ECS and EKS support

## Credits

Created with Cookiecutter using
[https://github.com/audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage)

<!--intro-end-->
