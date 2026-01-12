"""Top-level package for Shuuten Signal."""
from __future__ import annotations

__author__ = """Ritvik Nag"""
__email__ = 'me@ritviknag.com'

__all__ = [
    # base exports
    'setup',
    'init',
    'get_logger',
    # decorator(s)
    'capture',
    'wrap',
    # optional (if capture is not used)
    'detect_and_set_context',
    'reset_runtime_context',
    # logging functions
    'log', 'debug', 'info', 'warning',
    'error', 'exception', 'critical', 'fatal',
    # models
    'Config',
    # classes
    'ShuutenJSONFormatter',
    # version info
    'version',
]

from logging import Logger, NullHandler

from ._api import capture, get_logger, init, setup, wrap
from ._integrations import ShuutenJSONFormatter
from ._log import LOG
from ._models import Config
from ._runtime import detect_and_set_context, reset_runtime_context

_log: Logger | None = None

# Set up logging to ``/dev/null`` like a library is supposed to.
# http://docs.python.org/3.3/howto/logging.html#configuring-logging-for-a-library
LOG.addHandler(NullHandler())


def version():
    from importlib.metadata import version as _version
    return _version('shuuten')


def _get_shuuten_logger() -> Logger:
    global _log

    if _log is None:
        init()
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
