# History

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
