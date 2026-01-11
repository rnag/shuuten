"""Top-level package for Shuuten Signal."""
from __future__ import annotations

__author__ = """Ritvik Nag"""
__email__ = 'me@ritviknag.com'

__all__ = [
    'setup',
    'init',
    'get_logger',
    # decorator
    'capture',
    # optional (if catch is not used)
    'set_lambda_context',
    'set_runtime_context',
    'reset_runtime_context',
    # TODO remove
    'send_to_slack',
    # Classes
    'Notifier',
    'SlackWebhookDestination',
    'ShuutenJSONFormatter',
    'log', 'debug', 'info', 'warning', 'debug',
    'exception', 'critical', 'fatal',
]

from logging import Logger, NullHandler
from os import getenv

from ._client import Notifier, setup, capture, init, get_logger
from ._constants import ENV_ENV_VAR
from ._log import LOG
from ._models import from_lambda_context
from ._requests import send_to_slack
from ._runtime import (set_lambda_context,
                       set_runtime_context,
                       reset_runtime_context)
from ._destinations import SlackWebhookDestination
from ._integrations import ShuutenJSONFormatter


_log: Logger | None = None

# Set up logging to ``/dev/null`` like a library is supposed to.
# http://docs.python.org/3.3/howto/logging.html#configuring-logging-for-a-library
LOG.addHandler(NullHandler())


def version():
    from importlib.metadata import version
    __version__ = version('shuuten')
    return __version__


def _get_shuuten_logger() -> Logger:
    global _log

    if _log is not None:
        return _log

    # Lazy init with safe defaults
    init(app_name='shuuten', env=getenv(ENV_ENV_VAR) or 'dev')
    _log = get_logger('shuuten', configure_root=False)

    return _log


def critical(msg, *args, **kwargs):
    """
    Log a message with severity 'CRITICAL' on the Shuuten logger, which
    comes with pre-defined handler(s) added.
    """
    _get_shuuten_logger().critical(msg, *args, **kwargs)


def fatal(msg, *args, **kwargs):
    """
    Don't use this function, use critical() instead.
    """
    critical(msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    """
    Log a message with severity 'ERROR' on the Shuuten logger, which
    comes with pre-defined handler(s) added.
    """
    _get_shuuten_logger().error(msg, *args, **kwargs)


def exception(msg, *args, exc_info=True, **kwargs):
    """
    Log a message with severity 'ERROR' on the Shuuten logger, which
    comes with pre-defined handler(s) added.
    """
    error(msg, *args, exc_info=exc_info, **kwargs)


def warning(msg, *args, **kwargs):
    """
    Log a message with severity 'WARNING' on the Shuuten logger, which
    comes with pre-defined handler(s) added.
    """
    _get_shuuten_logger().warning(msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    """
    Log a message with severity 'INFO' on the Shuuten logger, which
    comes with pre-defined handler(s) added.
    """
    _get_shuuten_logger().info(msg, *args, **kwargs)


def debug(msg, *args, **kwargs):
    """
    Log a message with severity 'DEBUG' on the Shuuten logger, which
    comes with pre-defined handler(s) added.
    """
    _get_shuuten_logger().debug(msg, *args, **kwargs)


def log(level, msg, *args, **kwargs):
    """
    Log 'msg % args' with the integer severity 'level' on the Shuuten
    logger, which comes with pre-defined handler(s) added.
    """
    _get_shuuten_logger().log(level, msg, *args, **kwargs)
