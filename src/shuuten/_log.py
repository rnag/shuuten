# noinspection PyProtectedMember
from logging import ERROR, WARNING, _nameToLevel, getLogger

LOG = getLogger('shuuten')


def quiet_third_party_logs(level: int = WARNING) -> None:
    # boto3 chatty stack
    for name in (
        'botocore',
        'botocore.hooks',
        'botocore.endpoint',
        'botocore.auth',
        'boto3',
        'urllib3',
        'requests',
        's3transfer',
    ):
        getLogger(name).setLevel(level)


def level_to_int(level: 'str | int') -> int:
    if isinstance(level, int):
        return level

    return _nameToLevel.get(level.upper(), ERROR)
