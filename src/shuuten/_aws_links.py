from __future__ import annotations

from urllib.parse import quote

AWS_CONSOLE = 'https://console.aws.amazon.com'


def lambda_console_link(region: str, function_name: str) -> str:
    # Matches the style you used before :contentReference[oaicite:11]{index=11}
    return f'{AWS_CONSOLE}/lambda/home?region={quote(region)}#/functions/{quote(function_name)}'


def cloudwatch_log_stream_link(region: str, log_group: str, log_stream: str | None = None) -> str:
    # Common deep link pattern :contentReference[oaicite:12]{index=12}
    # Encode group/stream because they often contain "/" and "[]"
    group = quote(log_group, safe='')
    if log_stream:
        stream = quote(log_stream, safe='')
        return f'{AWS_CONSOLE}/cloudwatch/home?region={quote(region)}#logEventViewer:group={group};stream={stream}'

    return f'{AWS_CONSOLE}/cloudwatch/home?region={quote(region)}#logEventViewer:group={group}'
