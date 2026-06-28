# History

## 0.6.0 (2026-06-27)

### Added

- Deferred delivery mode for grouped Slack, Microsoft Teams, and email notifications
- `local_only` delivery mode for local structured logs without destination notifications
- `capture()` context manager support via `with shuuten.capture(...)`
- `SHUUTEN_DELIVERY_MODE` configuration option

### Changed

- Deferred notifications now group captured logs, context, and exception details into one destination message
- Improved grouped notification formatting across Slack, Microsoft Teams, and email

## 0.5.0 (2026-06-24)

### Added

- First-class structlog integration via `ShuutenProcessor`
- `configure_structlog()` helper for quick setup
- `shuuten_processors()` helper for advanced customization
- Support for forwarding structlog events to configured destinations
- Optional call-site metadata enrichment (`filename`, `lineno`, `func_name`, `module`)

### Changed

- `ShuutenProcessor` inherits `min_level` from `shuuten.Config` by default
- Local notifier re-emission is disabled for structlog notifications to prevent duplicate log output

### Documentation

- Added structlog integration documentation and examples
- Added installation instructions for `shuuten[structlog]`

## 0.4.0 (2026-06-21)

### Added

* Microsoft Teams destination via Incoming Webhooks using Adaptive Cards.
* `SHUUTEN_TEAMS_WEBHOOK_URL` configuration option.
* Rich Microsoft Teams notifications with structured event details, exception traces, AWS metadata, and deep links to CloudWatch and source code.
* Notification context propagation for `workflow`, `action`, and `run_id`, allowing logs emitted within `@capture()` to be correlated with the resulting failure notification.

### Changed

* Renamed `SlackNotificationHandler` to `ShuutenNotificationHandler` (backwards-compatible alias retained).
* Notification deduplication now applies across all configured destinations rather than being documented as Slack-specific.
* README refreshed to document Microsoft Teams support and destination-agnostic alerting.

### Fixed

* Logs emitted inside a `@capture()` scope now inherit the active workflow and action metadata.
* Improved consistency of notification metadata across Slack, Microsoft Teams, and SES destinations.

## 0.3.1 (2026-06-18)

### Changed
- Updated package description and README tagline to better reflect the library's purpose.
- Added `py.typed` marker for PEP 561 compliance — type checkers now recognize shuuten as a typed package.
- Added classifiers: `Topic :: Communications :: Chat`, `Topic :: Internet`, `Typing :: Typed`.
- Updated roadmap with concrete planned destinations (MS Teams, PagerDuty, JSM Alerting, structlog).

## 0.3.0 (2026-06-18)

### Added
- `ShuutenJSONFormatter` now supports `extra={'data': {...}}` to merge arbitrary fields
  top-level into the JSON log output, making structured logging cleaner in CloudWatch.
- `ShuutenJSONFormatter` now embeds `dict` and `list` values passed directly as `msg`
  as native JSON objects rather than stringified representations.
- `info_json()`, `debug_json()`, and `error_json()` convenience functions for structured
  logging via the `shuuten.*` module-level API.
- `SlackNotificationHandler` now also picks up `extra={'data': {...}}` and merges it
  into the event context forwarded to Slack.

### Changed
- `_BASE_LOG_KEYS` constant defined in `_integrations/_logging.py` to guard against
  key conflicts in `data` extra.

### Fixed
- Passing reserved `data` keys that conflict with built-in log output fields now raises
  a clear `ValueError` instead of silently overwriting output fields.

## 0.2.0 (2026-01-12)

### Added
- New high-level public API: `setup()`, `init()`, `get_logger()`, `capture()` / `wrap()` and runtime context helpers.
- Slack destination via Incoming Webhooks, including formatting options (`blocks` vs `plain`) and basic deduping (`SHUUTEN_DEDUPE_WINDOW_S`).
- Email destination via AWS SES (HTML email), configurable via `SHUUTEN_SES_*`.
- Support for AWS ECS Tasks.
- Docs site powered by MkDocs Material, with docs pages for README / contributing / history via include-markdown.

### Changed
- Project structure refactor: split out notifier, destinations, integrations, env helpers, runtime context, and models into dedicated modules.
- README refresh + clearer Quickstart / configuration tables.
- Improved environment variable parsing and configuration overlay behavior.

### Fixed
- Email/SES integration no longer imports `boto3` at top-level (library can be used without boto3 unless SES is enabled).
- Various Ruff linting fixes and small docs/build tweaks.

## 0.1.1 (2026-01-08)

* Publish docs site
* Update `README.md`

## 0.1.0 (2026-01-08)

* First release on PyPI.
