from __future__ import annotations

from dataclasses import dataclass, field
from os import getenv
from time import time
from typing import Any
from uuid import uuid4

from ._aws_links import cloudwatch_log_stream_link, lambda_console_link
from ._log import LOG
from ._requests import http_get_json


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
        src = event.source
        if not src:
            src = event.source = self.base_source()
            # unique to each invocation
            if self.request_id:
                src['request_id'] = self.request_id
            if self.log_stream:
                src['log_stream'] = self.log_stream

        # Link to AWS Lambda function
        if fn_url := self.function_url:
            src['function_url'] = fn_url

        # Canonical Link to CloudWatch Logs
        if not event.log_url and (log_url := self.log_url):
            event.log_url = log_url


def sniff_region() -> str | None:
    # AWS Region, should be automatically set for AWS Lambda functions
    return getenv('AWS_REGION') or getenv('AWS_DEFAULT_REGION')


def detect_context() -> RuntimeContext:
    """
    if no context is explicitly set:
        detect Lambda by AWS_LAMBDA_FUNCTION_NAME
        detect ECS by ECS_CONTAINER_METADATA_URI_V4
        else local
    """
    lambda_fn_name = getenv('AWS_LAMBDA_FUNCTION_NAME')
    ecs_metadata = getenv('ECS_CONTAINER_METADATA_URI_V4')

    if lambda_fn_name:
        return from_lambda_context(None, lambda_fn_name)

    if ecs_metadata:
        ctx = from_ecs(ecs_metadata)
        return ctx or from_local()

    return from_local()


def from_lambda_context(context: Any, fn_name: str | None = None) -> RuntimeContext:
    region = sniff_region()

    account_name = getenv('AWS_ACCOUNT_NAME')
    source_code = getenv('SOURCE_CODE')

    fn = fn_name or getattr(context, 'function_name', None) or getenv('AWS_LAMBDA_FUNCTION_NAME')
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
        function_name=fn,
        request_id=req,
        log_group=lg,
        log_stream=ls,
        cluster_name=None,
        task_arn=None,
    )


def _parse_arn_region_account(arn: str) -> tuple[str | None, str | None]:
    # arn:partition:service:region:account-id:resource
    parts = arn.split(':')
    if len(parts) >= 6:
        return parts[3] or None, parts[4] or None
    return None, None


def from_ecs(ecs_metadata: str | None = None) -> RuntimeContext | None:
    base = ecs_metadata or getenv('ECS_CONTAINER_METADATA_URI_V4')
    if not base:
        docs_link = ('https://docs.aws.amazon.com/AmazonECS/latest/userguide/'
                     'task-metadata-endpoint-v4-fargate.html')
        LOG.info(
            f'Environment variable "ECS_CONTAINER_METADATA_URI_V4" not defined '
            'in task; consider updating to platform version 1.4.0 to enable '
            'this feature. Please refer to the following docs:\n'
            f'  {docs_link}')
        return None

    account_name = getenv('AWS_ACCOUNT_NAME')
    source_code = getenv('SOURCE_CODE')

    # Best-effort region fallback (task arn is better)
    region = sniff_region()

    # Canonical ECS task document
    task_doc = http_get_json(f'{base}/task')
    container_doc = http_get_json(base)

    task_arn = task_doc.get('TaskARN')
    cluster = task_doc.get('Cluster')  # sometimes ARN, sometimes name

    account_id = None
    if isinstance(task_arn, str):
        arn_region, arn_account = _parse_arn_region_account(task_arn)
        region = arn_region or region
        account_id = arn_account or account_id

    # Container logging info (varies by log driver)
    # TODO unsure if set
    log_group = getenv('AWS_LOG_GROUP')
    log_stream = None

    # For awslogs driver, ECS metadata usually exposes LogOptions
    log_options = container_doc.get('LogOptions') or {}
    if isinstance(log_options, dict):
        log_group = log_options.get('awslogs-group') or log_group
        log_stream = log_options.get('awslogs-stream') or log_stream
        region = log_options.get('awslogs-region') or region

    # image = container_doc.get('Image')
    # if image:
    #     # optionally parse
    #     ...

    return RuntimeContext(
        platform='ecs',
        region=region,
        account_id=account_id,
        account_name=account_name,
        source_code=source_code,
        function_name=None,
        request_id=None,
        log_group=log_group,
        log_stream=log_stream,
        cluster_name=cluster,
        task_arn=task_arn,
    )


def from_local() -> RuntimeContext:

    return RuntimeContext(
        platform='local',
        region=sniff_region(),
        account_id=None,
        account_name=getenv('AWS_ACCOUNT_NAME'),
        source_code=getenv('SOURCE_CODE'),
        function_name=None,
        request_id=None,
        log_group=None,
        log_stream=None,
        cluster_name=None,
        task_arn=None,
    )
