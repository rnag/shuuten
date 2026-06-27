from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape as h

from .._formatting import (
    alert_details,
    format_alert_location,
    format_alert_title,
    get_group_alerts,
    is_grouped_event,
)
from .._models import Event


def _level_color(level: str) -> str:
    level = (level or '').upper()
    return {
        'DEBUG': '#1E90FF',
        'INFO': '#2E8B57',
        'WARNING': '#FF8C00',
        'ERROR': '#FF0000',
        'CRITICAL': '#8B0000',
    }.get(level, '#8B0000')


def _subject_for_event(event: Event) -> str:
    lvl = event.level or 'ERROR'
    env = event.env or '-'
    wf = event.workflow or '-'
    action = event.action or '-'

    app = (event.context or {}).get('app')
    app_part = f'[{app}] ' if app else ''

    return f'{lvl} {app_part}{env} {wf}: {action}'


def _compact_json(value: object, *, limit: int = 4000) -> str:
    text = json.dumps(value, indent=2, default=str, ensure_ascii=False)
    if len(text) > limit:
        return text[:limit] + '\n…[TRUNCATED]'
    return text


def _text_alerts(event: Event) -> list[str]:
    lines: list[str] = []
    alerts = get_group_alerts(event)

    if not alerts:
        return lines

    lines.append('')
    lines.append('alerts:')

    for i, alert in enumerate(alerts[:10], start=1):
        level = str(alert.get('level', '')).upper()
        title = format_alert_title(alert)
        loc = format_alert_location(alert)
        details = alert_details(alert)
        traceback_text = alert.get('traceback')

        lines.append(f'  {i}. {level}')
        if loc:
            lines.append(f'     location: {loc}')
        lines.append(f'     message: {title}')

        if details:
            lines.append('     context:')
            for line in _compact_json(details, limit=1200).splitlines():
                lines.append(f'       {line}')

        if traceback_text:
            lines.append('     traceback:')
            for line in str(traceback_text)[-3000:].splitlines():
                lines.append(f'       {line}')

    if len(alerts) > 10:
        lines.append(f'  … {len(alerts) - 10} more alerts')

    return lines


def _text_body(event: Event) -> str:
    # plaintext fallback (always include)
    app = (event.context or {}).get('app')
    lines = [
        f'{event.summary}',
        f'level={event.level} app={app} env={event.env}',
        f'workflow={event.workflow} action={event.action}',
        f'run_id={event.run_id}',
    ]

    if event.log_url:
        lines.append(f'logs: {event.log_url}')

    if event.source:
        lines.append('source:')
        for k, v in event.source.items():
            lines.append(f'  {k}: {v}')

    if is_grouped_event(event):
        lines.extend(_text_alerts(event))
    elif event.message:
        lines.append('')
        lines.append('message:')
        lines.append(event.message)

    context_for_email = dict(event.context or {})
    for k in ('app', 'logger', 'file', 'lineno', 'func', 'alerts'):
        context_for_email.pop(k, None)

    if context_for_email:
        lines.append('')
        lines.append('context:')
        for k, v in context_for_email.items():
            lines.append(f'  {k}: {v}')

    if event.exception:
        lines.append('')
        lines.append('exception:')
        lines.append(event.exception)

    return '\n'.join(lines)


def _html_body(event: Event) -> str:
    # Keep it simple (no external fonts/css needed)
    # Email clients are picky; inline-ish styling is safer.
    ctx_app = (event.context or {}).get('app')
    esc_app = h(ctx_app) if ctx_app else ''
    esc_env = h(event.env or '')
    esc_action = h(event.action or '')
    esc_workflow = h(event.workflow or '')

    def row(k: str, v: str) -> str:
        return f"""
        <tr>
          <td style='padding:6px 10px;color:#555;font-size:12px;vertical-align:top;white-space:nowrap;'><b>{k}</b></td>
          <td style='padding:6px 10px;color:#111;font-size:12px;vertical-align:top;'>{v}</td>
        </tr>
        """  # noqa: E501

    rows = [
        row('Level', h(event.level)),
        row('Env', esc_env),
        row('Workflow', esc_workflow),
        row('Action', esc_action),
        row('Run ID', h(event.run_id)),
        row('Timestamp', str(event.timestamp)),
    ]
    if esc_app:
        rows.append(row('App', esc_app))

    meta_rows = ''.join(rows)

    links = ''
    if event.log_url:
        links += f'<div style="margin:6px 0;"><a href="{h(event.log_url)}">CloudWatch Logs</a></div>'  # noqa: E501
    src = event.source
    if isinstance(src, dict) and src.get('function_url'):
        links += f'<div style="margin:6px 0;"><a href="{h(src["function_url"])}">Lambda</a></div>'  # noqa: E501
    if isinstance(src, dict) and src.get('source_code'):
        links += f'<div style="margin:6px 0;"><a href="{h(src["source_code"])}">Source</a></div>'  # noqa: E501

    # Render source/context tables compactly
    def table_from_dict(d: dict) -> str:
        if not d:
            return '<i>none</i>'
        rows = ''.join(row(h(str(k)), h(str(v))) for k, v in d.items())
        return (
            '<table style="border-collapse:collapse;width:100%;'
            f'background:#fff;border:1px solid #eee;">{rows}</table>'
        )

    def pre_block(text: str, *, dark: bool = False) -> str:
        bg = '#0b0b0b' if dark else '#f2f3f5'
        color = '#f5f5f5' if dark else '#111'
        return (
            f'<pre style="white-space:pre-wrap;background:{bg};color:{color};'
            'padding:12px;border-radius:6px;font-size:12px;overflow:auto;">'
            f'{h(text)}</pre>'
        )

    def alerts_html() -> str:
        alerts = get_group_alerts(event)
        if not alerts:
            return ''

        parts = ['<h3 style="margin:16px 0 8px 0;">Alerts captured</h3>']

        for i, alert in enumerate(alerts[:10], start=1):
            level = str(alert.get('level', '')).upper()
            color = _level_color(level)
            title = format_alert_title(alert)
            loc = format_alert_location(alert)
            details = alert_details(alert)
            traceback_text = alert.get('traceback')

            parts.append(
                f"""
                <div style="border:1px solid #e5e5e5;border-left:5px solid {color};border-radius:8px;margin:10px 0;padding:12px;background:#fff;">
                  <div style="font-size:13px;font-weight:700;color:{color};margin-bottom:6px;">
                    {i}. {h(level)}
                  </div>
                """  # noqa: E501
            )

            if loc:
                parts.append(
                    f'<div style="font-size:12px;color:#666;margin-bottom:8px;"><code>{h(loc)}</code></div>'  # noqa: E501
                )

            if title:
                parts.append(
                    '<div style="font-size:12px;font-weight:700;margin:8px 0;">Message</div>'  # noqa: E501
                )
                parts.append(pre_block(title))

            if details:
                parts.append(
                    '<div style="font-size:12px;font-weight:700;margin:8px 0;">Context</div>'  # noqa: E501
                )  # noqa: E501
                parts.append(pre_block(_compact_json(details, limit=1500)))

            if traceback_text:
                parts.append(pre_block(str(traceback_text)[-3500:], dark=True))

            parts.append('</div>')

        if len(alerts) > 10:
            parts.append(
                f'<div style="font-size:12px;color:#666;">… {len(alerts) - 10} more alerts</div>'  # noqa: E501
            )

        return ''.join(parts)

    exc_block = ''
    if event.exception:
        exc = event.exception
        if len(exc) > 12000:
            exc = exc[-12000:]
        exc_block = f"""
        <h3 style='margin:16px 0 8px 0;'>Exception</h3>
        {pre_block(exc, dark=True)}
        """  # noqa: E501

    color = _level_color(event.level)

    msg_block = ''
    if event.message and not is_grouped_event(event):
        msg = event.message
        if len(msg) > 4000:
            msg = msg[:4000] + '\n…(truncated)…'
        msg_block = f"""
          <h3 style="margin:16px 0 8px 0;">Message</h3>
          {pre_block(msg)}
        """

    context_for_email = dict(event.context or {})
    for k in ('app', 'logger', 'file', 'lineno', 'func', 'alerts'):
        context_for_email.pop(k, None)

    return f"""
    <html>
      <body style="font-family:Arial, sans-serif;background:#f6f7f9;padding:16px;">
        <div style="max-width:720px;margin:0 auto;background:#fff;border:1px solid #e6e6e6;border-radius:10px;overflow:hidden;">
          <div style="background:{color};color:#fff;padding:12px 16px;">
            <div style="font-size:16px;font-weight:700;">{h(event.summary)}</div>
            <div style="font-size:12px;opacity:0.9;">{h(event.level)} · {esc_env} · {esc_workflow} · {esc_action}</div>
          </div>

          <div style="padding:16px;">
            {msg_block}

            <h3 style="margin:0 0 8px 0;">Summary</h3>
            <table style="border-collapse:collapse;width:100%;background:#fff;border:1px solid #eee;">
              {meta_rows}
            </table>

            {('<h3 style="margin:16px 0 8px 0;">Links</h3>' + links) if links else ''}

            {alerts_html() if is_grouped_event(event) else ''}

            <h3 style="margin:16px 0 8px 0;">Source</h3>
            {table_from_dict(event.source)}

            <h3 style="margin:16px 0 8px 0;">Context</h3>
            {table_from_dict(context_for_email)}

            {exc_block}
          </div>
        </div>
      </body>
    </html>
    """  # noqa: E501


@dataclass(slots=True, frozen=True)
class SESDestination:
    from_address: str
    to_addresses: list[str]
    reply_to: list[str]
    region_name: str | None = None  # optional override

    def _client(self):
        try:
            import boto3  # type: ignore[unresolved-import]
        except ImportError as e:
            raise RuntimeError(
                'boto3 is required for SES email delivery. '
                'Install it or disable email notifications.'
            ) from e

        if self.region_name:
            return boto3.client('ses', region_name=self.region_name)
        return boto3.client('ses')

    def send(self, event: Event, *, exc_text: str | None = None) -> None:
        if not self.to_addresses:
            return

        safe = event.safe(exception=exc_text)

        subject = _subject_for_event(safe)
        text = _text_body(safe)
        html = _html_body(safe)

        client_kwargs = {
            'Source': self.from_address,
            'Destination': {'ToAddresses': self.to_addresses},
            'Message': {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text, 'Charset': 'UTF-8'},
                    'Html': {'Data': html, 'Charset': 'UTF-8'},
                },
            },
        }

        if self.reply_to:
            client_kwargs['ReplyToAddresses'] = self.reply_to

        self._client().send_email(**client_kwargs)
