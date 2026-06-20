__all__ = [
    'SESDestination',
    'SlackWebhookDestination',
    'MSTeamsWebhookDestination',
]

from ._email import SESDestination
from ._slack import SlackWebhookDestination
from ._teams import MSTeamsWebhookDestination
