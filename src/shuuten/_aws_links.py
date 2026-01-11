from __future__ import annotations

from urllib.parse import quote

AWS_CONSOLE = 'https://console.aws.amazon.com'


def lambda_console_link(region: str, function_name: str) -> str:
    return (f'{AWS_CONSOLE}/lambda/home?region={quote(region)}'
            f'#/functions/{quote(function_name)}')


def cloudwatch_log_stream_link(region: str,
                               log_group: str,
                               log_stream: str | None = None) -> str:
    # Common deep link pattern
    # Encode group/stream because they often contain "/" and "[]"
    group = quote(log_group, safe='')
    if log_stream:
        stream = quote(log_stream, safe='')
        return (f'{AWS_CONSOLE}/cloudwatch/home?region={quote(region)}'
                f'#logEventViewer:group={group};stream={stream}')

    return (f'{AWS_CONSOLE}/cloudwatch/home?region={quote(region)}'
            f'#logEventViewer:group={group}')
