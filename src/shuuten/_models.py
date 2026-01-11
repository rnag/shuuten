from __future__ import annotations

from dataclasses import dataclass, field, fields, replace, MISSING
from enum import Enum
from logging import WARNING, ERROR
from os import getenv
from time import time
from typing import Any, cast, Literal
from uuid import uuid4

from ._aws_links import cloudwatch_log_stream_link, lambda_console_link
from ._env_helpers import split_emails
from ._log import LOG
from ._redact import redact
from ._requests import http_get_json


def _redact_optional(s: str | None) -> str | None:
    return redact(s) if s else None


SLACK_FORMAT_TYPE = Literal['blocks', 'plain']


class Platform(str, Enum):
    AUTO = 'auto'
    LAMBDA = 'lambda'
    ECS = 'ecs'


@dataclass(slots=True)
class ShuutenConfig:
    app: str | None = None
    env: str | None = None

    emit_local_log: bool = True
    quiet_level: int | None = WARNING
    # Slack webhook
    slack_webhook_url: str | None = None
    slack_format: SLACK_FORMAT_TYPE = 'blocks'

    # Minimum log level for messages sent to Slack
    min_level: int = ERROR

    # SES outbound email address
    ses_from: str | None = None
    # Comma-delimited field, if provided will send stylized HTML to them
    #
    # Example:
    #   'user1@my.domain.org,user2@my.domain.org'
    ses_to: list[str] = field(default_factory=list)
    ses_reply_to: list[str] = field(default_factory=list)
    ses_region: str | None = None

    def with_env_defaults(self) -> ShuutenConfig:
        cfg = ShuutenConfig.from_env()
        return cfg.overlay(self)

    def overlay(self, other: ShuutenConfig) -> ShuutenConfig:
        """
        Return a new config where `other` overrides `self`.
        Semantics:
          - quiet_level: None is an explicit override meaning "disable"
          - strings: None means "no override"
          - lists: empty list means "no override" (see note)
          - bool/int: always override if different? (we handle explicitly)
        """
        out = replace(self)

        # Scalars: None => no override
        # Strings with defaults: override if not None (even if "")
        # Int policy: always override (min_level is not Optional)
        for name in ('app', 'env', 'slack_webhook_url', 'ses_from',
                     'ses_region', 'slack_format', 'min_level'):
            v = getattr(other, name)
            if v is not None:
                setattr(out, name, v)

        # quiet_level: None is meaningful (explicit disable)
        # so we must always take it when user passes it.
        #
        # Problem: can't tell if they passed it explicitly.
        # Solution: require user to pass quiet_level explicitly when calling init,
        # or move to UNSET sentinel for full correctness.
        out.quiet_level = other.quiet_level

        # Lists: treat empty as "no override"
        if other.ses_to:
            out.ses_to = list(other.ses_to)
        if other.ses_reply_to:
            out.ses_reply_to = list(other.ses_reply_to)

        # Bool: override
        out.emit_local_log = other.emit_local_log

        return out

    @classmethod
    def from_env(cls) -> ShuutenConfig:
        # TODO maybe Enum
        slack_format = cast(SLACK_FORMAT_TYPE, getenv('SHUUTEN_SLACK_FORMAT', 'blocks'))
        min_lvl_from_env = getenv('SHUUTEN_MIN_LEVEL')
        emit_local_log_from_env = getenv('SHUUTEN_EMIT_LOCAL_LOG')
        emit_local_log = True if (
            emit_local_log_from_env is None
            or emit_local_log_from_env.upper() in ('1', 'TRUE', 'YES')
        ) else False

        return cls(
            app=getenv('SHUUTEN_APP'),
            env=getenv('SHUUTEN_ENV'),
            emit_local_log=emit_local_log,
            quiet_level=getenv('SHUUTEN_QUIET_LEVEL', WARNING),
            min_level=int(min_lvl_from_env) if min_lvl_from_env else ERROR,
            slack_webhook_url=getenv('SHUUTEN_SLACK_WEBHOOK_URL'),
            slack_format=slack_format,
            ses_from=getenv('SHUUTEN_SES_FROM'),
            ses_to=split_emails(getenv('SHUUTEN_SES_TO')),
            ses_reply_to=split_emails(getenv('SHUUTEN_SES_REPLY_TO')),
            ses_region=getenv('SHUUTEN_SES_REGION'),
        )


@dataclass(slots=True)
class Event:
    level: str                    # 'ERROR' | 'WARNING' | 'INFO'
    summary: str                  # "Automation failed" / "Log forwarded"
    message: str | None = None    # actual log line or str(exc)

    # TODO
    env: str | None = None        # if None, renderer can use config env ('prod')

    # (optional) classification stream: `logs`, `sync`, `photos`, etc.
    workflow: str | None = None
    # fn qualname or logger name (optional)
    action: str | None = None

    run_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time)

    # 'safe' identifiers (prefer IDs, not emails)
    subject_id: str | None = None
    # free-form structured context
    context: dict[str, Any] = field(default_factory=dict)

    # links / metadata
    source: dict[str, Any] = field(default_factory=dict)
    # (optional) deep link to CW
    log_url: str | None = None

    exception: str | None = None

    def safe(self, *, exception: str | None = None) -> Event:
        # Make a shallow copy first
        e = replace(self)

        exc = exception if exception is not None else self.exception

        # Redact string-ish fields
        e.summary = redact(self.summary) if self.summary else ''
        e.message = _redact_optional(self.message)
        e.workflow = _redact_optional(self.workflow)
        e.action = _redact_optional(self.action)
        e.env = _redact_optional(self.env)
        e.subject_id = _redact_optional(self.subject_id)
        e.log_url = _redact_optional(self.log_url)
        e.exception = redact(exc) if exc else None

        # Redact structured fields (should be deep/recursive in your redact())
        e.context = redact(self.context) if self.context else {}
        e.source = redact(self.source) if self.source else {}

        # uppercase level
        e.level = e.level.upper()

        return e


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    platform: str                  # 'lambda' | 'ecs' | 'local'
    region: str | None
    account_id: str | None
    # from env
    account_name: str | None
    # Optional link to source code repo for the project
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


def detect_context(
        context=None,
        platform: Platform = Platform.AUTO,
) -> RuntimeContext:
    """
    if no context is explicitly set:
        detect Lambda by AWS_LAMBDA_FUNCTION_NAME
        detect ECS by ECS_CONTAINER_METADATA_URI_V4
        else local
    """
    lambda_fn_name = getenv('AWS_LAMBDA_FUNCTION_NAME')
    ecs_metadata = getenv('ECS_CONTAINER_METADATA_URI_V4')

    if lambda_fn_name or platform is Platform.LAMBDA:
        return from_lambda_context(context, lambda_fn_name)

    if ecs_metadata or platform is Platform.ECS:
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
    log_group = None
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
