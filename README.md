<div align="center">
<img alt="logo" width="175" src="https://raw.githubusercontent.com/rnag/shuuten/main/img/logo.png">

## Shuuten Signal

[![PyPI version](https://img.shields.io/pypi/v/shuuten.svg)](https://pypi.org/project/shuuten)
[![PyPI license](https://img.shields.io/pypi/l/shuuten.svg)](https://pypi.org/project/shuuten)
[![PyPI Python versions](https://img.shields.io/pypi/pyversions/shuuten.svg)](https://pypi.org/project/shuuten)
[![GitHub Actions](https://github.com/rnag/shuuten/actions/workflows/release.yml/badge.svg)](https://github.com/rnag/shuuten/actions/workflows/release.yml)
[![Documentation Status](https://github.com/rnag/shuuten/actions/workflows/gh-pages.yml/badge.svg)](https://shuuten.ritviknag.com)

</div>

<!--intro-start-->

**Last-stop signals for automation failures.**

*終点 (Shuuten) means “final stop” or “terminus” in Japanese — the point where a workflow ends and signals that something needs attention.*

> 終点 (Shuuten): the final stop — where automations end and signal for attention.

📖 Docs: [shuuten.ritviknag.com](https://shuuten.ritviknag.com) · ⭐ Star: [GitHub](https://github.com/rnag/shuuten)

---

**Batteries included, zero-dependency, and lightweight.**

AWS Lambda example --
`export SHUUTEN_SLACK_WEBHOOK_URL='...'` (as per [docs](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)) before.

```python3
import shuuten

@shuuten.capture  # or: capture(workflow='my-example-lambda')
def lambda_handler(event, context):
    shuuten.debug('test')  # not sent to Slack
    shuuten.error('AN ERROR!')  # ERROR+: by default sent to Slack + email if configured
    shuuten.warning("Calling other_func", extra={"shuuten": {"caller": "my_fn"}})  # not sent
    shuuten.info('TEST', stack_info=True)  # not sent
    1 / 0   # sends to Slack + email with trace
```

## About

Shuuten Signal provides structured, safe failure notifications for Python automations running in AWS Lambda, ECS, and beyond.

## Features

- Dependency-free Slack Incoming Webhook notifications
- Designed for AWS Lambda, ECS, and container-based automations
- Configured for Destinations: (1) Slack and (2) Email via SES (more to come)
- Minimal surface area, easy to extend

## Install

```shell
pip install shuuten
```

## Usage

AWS Lambda, most "easy to get started" example, similar to `logging`:
```python3
import shuuten

hook_url = "https://hooks.slack.com/services/<team>/<channel>/<token>"  # keep this secret
payload = {'text': 'Hello from Shuuten 👋 (webhook test)'}

def lambda_handler(event, context):
    shuuten.debug('test')  # not sent to Slack
    other_func()

def other_func():
    shuuten.error('AN ERROR!')  # ERROR+: by default sent to Slack if configured
    shuuten.warning("Calling other_func", extra={"shuuten": {"caller": "my_fn"}})  # not sent
    shuuten.info('TEST', stack_info=True)  # not sent
    1 / 0  # sends to Slack with trace
```

By default Shuuten emits a local structured log record whenever it sends a notification. Disable with `emit_local_log=False` if you only want external notifications.

To send to email, set `SHUUTEN_SES_FROM` + `SHUUTEN_SES_TO` and grant necesary permissions to AWS Lambda or whatever task. Then:

```python3
import shuuten


shuuten.init(shuuten.ShuutenConfig(app='my-app', env='dev'))
log = shuuten.get_logger(__name__)


@shuuten.capture(workflow='my-sample-workflow')
def handler(event, context):
    log.info('Hello world!')  # not sent
    log.critical('Something went wrong! Help!')  # ERROR+: Sent to Slack + Email
```

If you don't wanna use `capture()` decorator, then set/reset context manually for now (context manager coming soon!)
```python
import shuuten

def handler(event, context):
    token = shuuten.detect_and_set_context(context)
    try:
        ...
    finally:
        shuuten.reset_runtime_context(token)
```

The `capture()` decorator works for ECS Tasks too! It use the ECS Metadata endpoint v4.

## Config and Env Vars

Pass following config via `ShuutenConfig` as in `shuuten.init(config=...)` or else set in environment:

* `SHUUTEN_APP` - App name, mostly unused...
* `SHUUTEN_ENV` - Environment for AWS account (example: `prod | dev | staging | etc.`)
* `SHUUTEN_EMIT_LOCAL_LOG` - true for Shuuten to notify / log internal logs (local only) (default: `True`)
* `SHUUTEN_QUIET_LEVEL` - Quiet level for 3rd party libraries (such as botocore); defaults to `WARNING` if not set.
* `SHUUTEN_MIN_LEVEL` - Minimum log level for messages sent to destination(s) (default: `ERROR`)
* `SHUUTEN_SLACK_WEBHOOK_URL` - Slack webhook URL; If set, logs above `SHUUTEN_MIN_LEVEL` are sent to Slack
* `SHUUTEN_SLACK_FORMAT` Slack format for messages, either Block Kit or plain text (default: `blocks`)
* `SHUUTEN_SES_FROM` - SES identity or sender, must be verified in SES (example: `sender@my.domain.org`)
* `SHUUTEN_SES_TO` (`list[str]`) - Comma-delimited field, if provided will send stylized HTML to them
  * Example: `'user1@my.domain.org,user2@my.domain.org'`
* `SHUUTEN_SES_REPLY_TO` - Optional `Reply-To` address (example: `reply-to@my.domain.org`)
* `SHUUTEN_SES_REGION` - Optional AWS region
* `SHUUTEN_DEDUPE_WINDOW_S` - Dedupe window for logs to Slack, in seconds (default: `30.0`)

# Supported Destinations

* **Slack** (requires `SHUUTEN_SLACK_WEBHOOK_URL`)
* **Email** (requires `SHUUTEN_SES_FROM` and `SHUUTEN_SES_TO`)

## Future Work (Planned)

* Send to AWS Teams and PagerDuty and other destinations
* Maybe send to ElastiCache (ECS) too - not sure
* Context manager for exceptions
* Offer `exception_only: bool = False` to only send logs with `exc_info=True`
* ECS Agent for more streamlined and performance-based error reporting
* Support AWS EKS

## Credits

This package was created with [Cookiecutter](https://github.com/audreyfeldroy/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.

<!--intro-end-->
