"""Top-level package for Shuuten Signal."""

__author__ = """Ritvik Nag"""
__email__ = 'me@ritviknag.com'

__all__ = [
    'send_to_slack',
]

from .shuuten import send_to_slack


def version():
    from importlib.metadata import version
    __version__ = version('shuuten')
    return __version__
