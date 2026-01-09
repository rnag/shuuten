<div align="center">
<img alt="logo" width="175" src="https://raw.githubusercontent.com/rnag/shuuten/refs/heads/main/img/logo.png">

## Shuuten Signal

[![Build Status](https://github.com/rnag/shuuten/actions/workflows/test.yml/badge.svg)](https://github.com/rnag/shuuten/actions)
[![Latest Version](https://img.shields.io/pypi/v/shuuten.svg)](https://pypi.org/project/shuuten)
[![Python Version](https://img.shields.io/pypi/pyversions/shuuten.svg)](https://pypi.python.org/pypi/shuuten)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)

</div>

<!--intro-start-->

**Last-stop signals for automation failures.**

*終点 (Shuuten) means “final stop” or “terminus” in Japanese — the point where a workflow ends and signals that something needs attention.*

---

> 終点 (Shuuten): the final stop — where automations end and signal for attention.

## About

Shuuten Signal provides structured, safe failure notifications for Python automations running in AWS Lambda, ECS, and beyond.

In v0.1.0, Shuuten focuses on being a lightweight, dependency-free foundation for sending failure signals from automation workflows.

## Features

- Dependency-free Slack Incoming Webhook notifications
- Designed for AWS Lambda, ECS, and container-based automations
- Minimal surface area, easy to extend

## Install

```shell
pip install shuuten
```

## Usage

```python3
import shuuten

hook_url = "https://hooks.slack.com/services/<team>/<channel>/<token>"  # keep this secret
payload = {'text': 'Hello from Shuuten 👋 (webhook test)'}

shuuten.send_to_slack(hook_url, payload)
```

## Credits

This package was created with [Cookiecutter](https://github.com/audreyfeldroy/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.

<!--intro-end-->
