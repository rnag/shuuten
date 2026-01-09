"""Top-level package for Shuuten Signal."""

__author__ = """Ritvik Nag"""
__email__ = 'me@ritviknag.com'

__all__ = [
    'Notifier',
    'notify_exceptions',
    'SlackWebhookDestination',
    'ShuutenJSONFormatter',
    'send_to_slack',
]

from ._shuuten import send_to_slack
from ._client import Notifier, notify_exceptions
from ._destinations import SlackWebhookDestination
from ._integrations import ShuutenJSONFormatter


def version():
    from importlib.metadata import version
    __version__ = version('shuuten')
    return __version__
