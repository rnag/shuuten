"""Top-level package for Shuuten Signal."""

__author__ = """Ritvik Nag"""
__email__ = 'me@ritviknag.com'

__all__ = [
    'setup',
    'init',
    'catch',
    'get_logger',
    'Notifier',
    'SlackWebhookDestination',
    'ShuutenJSONFormatter',
    'send_to_slack',
]

from ._shuuten import send_to_slack
from ._client import Notifier, setup, catch, init, get_logger
from ._destinations import SlackWebhookDestination
from ._integrations import ShuutenJSONFormatter


def version():
    from importlib.metadata import version
    __version__ = version('shuuten')
    return __version__
