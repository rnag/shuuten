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

from logging import NullHandler

from ._client import Notifier, setup, catch, init, get_logger
from ._log import LOG
from ._models import from_lambda_context
from ._requests import send_to_slack
from ._runtime import set_lambda_context, set_runtime_context, reset_runtime_context
from ._destinations import SlackWebhookDestination
from ._integrations import ShuutenJSONFormatter

# Set up logging to ``/dev/null`` like a library is supposed to.
# http://docs.python.org/3.3/howto/logging.html#configuring-logging-for-a-library
LOG.addHandler(NullHandler())


def version():
    from importlib.metadata import version
    __version__ = version('shuuten')
    return __version__
