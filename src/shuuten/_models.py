from __future__ import annotations

from dataclasses import dataclass, field
from os import getenv
from time import time
from typing import Any
from uuid import uuid4

from ._aws_links import cloudwatch_log_stream_link, lambda_console_link


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
    source: dict[str, Any] = field(default_factory=dict)
    log_url: str | None = None      # deep link to CW (optional)


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    platform: str                  # 'lambda' | 'ecs' | 'local'
    region: str | None
    account_id: str | None
    # from env
    account_name: str | None
    source_code: str | None

    # Lambda
    function_name: str | None
    request_id: str | None
    log_group: str | None
    log_stream: str | None

    # ECS
    cluster_name: str | None
    task_arn: str | None

    @property
    def function_url(self):
        if self.function_name and self.region:
            return lambda_console_link(self.region, self.function_name)
        return None

    @property
    def log_url(self):
        if self.region and self.log_group:
            if self.log_stream:
                return cloudwatch_log_stream_link(
                    self.region, self.log_group, self.log_stream)
            else:
                return cloudwatch_log_stream_link(
                    self.region, self.log_group)
        return None

    @property
    def base_source(self) -> dict[str, Any]:
        src = {
            'platform': self.platform,
            'function_name': self.function_name,
            'region': self.region,
            'log_group': self.log_group,
            'cluster': self.cluster_name,
            'task_arn': self.task_arn,
            'account_name': self.account_name,
            'account_id': self.account_id,
            'source_code': self.source_code,
        }
        return {k: v for k, v in src.items() if v is not None}

    def enrich_event_source(self, event: Event):
        # Fill event.source / log_url if missing
        if not event.source:
            event.source = self.base_source.copy()
            # unique to each invocation
            if self.request_id:
                event.source['request_id'] = self.request_id
            if self.log_stream:
                event.source['log_stream'] = self.log_stream

        # Link to AWS Lambda function
        if fn_url := self.function_url:
            event.source['function_url'] = fn_url

        # Canonical Link to CloudWatch Logs
        if not event.log_url and (log_url := self.log_url):
            event.log_url = log_url


def sniff_region() -> str | None:
    # AWS Region, should be automatically set for AWS Lambda functions
    return getenv('AWS_REGION') or getenv('AWS_DEFAULT_REGION')


def from_lambda_context(context: Any) -> RuntimeContext:
    region = sniff_region()

    account_name = getenv('AWS_ACCOUNT_NAME')
    source_code = getenv('SOURCE_CODE')

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
        region=region,
        account_name=account_name,
        source_code=source_code,
        account_id=account_id,
        function_name=fn or getenv('AWS_LAMBDA_FUNCTION_NAME'),
        request_id=req,
        log_group=lg,
        log_stream=ls,
        cluster_name=None,
        task_arn=None,
    )


# def from_ecs() -> RuntimeContext | None:
#     base = getenv('ECS_CONTAINER_METADATA_URI_V4')
#     if not base:
#         return None
#
#     task = http_get_json(f'{base}/task')
#     container = http_get_json(base)
#
#     task_arn = task.get('TaskARN')
#     cluster = task.get('Cluster')
#
#     region = parse_region_from_arn(task_arn)  # arn:aws:ecs:REGION:ACCOUNT:...
#     account_id = parse_account_from_arn(task_arn)
#
#     # Best effort logs (varies a lot)
#     log_group, log_stream = try_extract_awslogs(container)  # maybe None
#
#     return RuntimeContext(
#         platform='ecs',
#         region=region,
#         account_id=account_id,
#         account_name=getenv('AWS_ACCOUNT_NAME'),
#         source_code=getenv('SOURCE_CODE'),
#         cluster_name=cluster,
#         task_arn=task_arn,
#         log_group=log_group,
#         log_stream=log_stream,
#         function_name=None,
#         request_id=None,
#         service=getenv('SERVICE_NAME') or getenv('APP_NAME'),
#     )
