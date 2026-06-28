from ._models import Event


def is_grouped_event(event: Event) -> bool:
    return isinstance((event.context or {}).get('alerts'), list)


def get_group_alerts(event: Event) -> list[dict]:
    alerts = (event.context or {}).get('alerts')
    return alerts if isinstance(alerts, list) else []


def format_alert_title(alert: dict) -> str:
    msg = alert.get('message') or alert.get('summary') or 'Alert'
    exc = alert.get('exception')
    return f'{msg} — {exc}' if exc else msg


def format_alert_location(alert: dict) -> str:
    if (file := alert.get('file')) and (line_no := alert.get('lineno')):
        return f'{file}:{line_no}'
    return ''


def alert_details(alert: dict) -> dict:
    return ctx if isinstance(ctx := alert.get('context'), dict) else {}
