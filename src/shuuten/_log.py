from logging import WARNING, getLogger

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
