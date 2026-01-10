"""Top-level package for Shuuten Signal."""

__author__ = """Ritvik Nag"""
__email__ = 'me@ritviknag.com'

__all__ = [
    'setup',
    'init',
    'get_logger',
    # decorator
    'catch',
    # optional (if catch is not used)
    'set_lambda_context',
    'set_runtime_context',
    'from_lambda_context',
    # TODO remove
    'send_to_slack',
    # Classes
    'Notifier',
    'SlackWebhookDestination',
    'ShuutenJSONFormatter',
]

from ._shuuten import send_to_slack
from ._client import Notifier, setup, catch, init, get_logger
from ._models import from_lambda_context
from ._runtime import set_lambda_context, set_runtime_context, reset_runtime_context
from ._destinations import SlackWebhookDestination
from ._integrations import ShuutenJSONFormatter


def version():
    from importlib.metadata import version
    __version__ = version('shuuten')
    return __version__
