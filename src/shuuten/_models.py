from __future__ import annotations

from dataclasses import dataclass, field
from os import getenv
from time import time
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Event:
    level: str              # 'ERROR' | 'WARNING' | 'INFO'
    title: str              # short human summary
    workflow: str           # 'slack-photo-sync'
    action: str             # 'upload_photo'
    env: str                # 'prod'
    run_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time)

    # 'safe' identifiers (prefer IDs, not emails)
    subject_id: str | None = None

    # free-form structured context
    context: dict[str, Any] = field(default_factory=dict)

    # links / metadata
    source: str | None = None       # 'lambda:funcname' or 'ecs:cluster/service'
    log_url: str | None = None      # deep link to CW (optional)


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    platform: str                  # 'lambda' | 'ecs' | 'local'
    service: str | None
    env: str | None
    region: str | None
    account_id: str | None

    # Lambda-ish
    function_name: str | None
    request_id: str | None
    log_group: str | None
    log_stream: str | None

    # ECS-ish
    cluster_name: str | None
    task_arn: str | None


def sniff_region() -> str | None:
    # AWS Region, should be automatically set for AWS Lambda functions
    return getenv('AWS_REGION') or getenv('AWS_DEFAULT_REGION', 'us-east-1')


def from_lambda_context(context: Any, *, service: str | None = None, env: str | None = None) -> RuntimeContext:
    region = sniff_region()

    fn = getattr(context, 'function_name', None)
    req = getattr(context, 'aws_request_id', None)
    lg = getattr(context, 'log_group_name', None) or getenv('AWS_LAMBDA_LOG_GROUP_NAME')
    ls = getattr(context, 'log_stream_name', None) or getenv('AWS_LAMBDA_LOG_STREAM_NAME')
    arn = getattr(context, 'invoked_function_arn', None)
    account_id = None
    if isinstance(arn, str):
        parts = arn.split(':')
        if len(parts) > 4:
            account_id = parts[4]

    return RuntimeContext(
        platform='lambda',
        service=service,
        env=env,
        region=region,
        account_id=account_id,
        function_name=fn or getenv('AWS_LAMBDA_FUNCTION_NAME'),
        request_id=req,
        log_group=lg,
        log_stream=ls,
        cluster_name=None,
        task_arn=None,
    )
