from logging import ERROR
from os import getenv


# Minimum level for library logs, to show up in CloudWatch
# LOG_CFG = getenv('SHUUTEN_LOG_CFG')

# AWS Account Alias (name), can be optionally set in the environment
#
# If defined, will be used instead of making a call to `iam:ListAccountAliases`
# to retrieve the alias of the current AWS account.
AWS_ACCOUNT_NAME = getenv('AWS_ACCOUNT_NAME')

# Minimum log level for messages sent to Slack
SLACK_MIN_LVL_ENV_VAR = 'SHUUTEN_SLACK_LOG_LVL'

# Slack webhook
SLACK_WEBHOOK_ENV_VAR = 'SHUUTEN_SLACK_WEBHOOK_URL'

# SES outbound email address
SES_FROM_ENV_VAR = 'SHUUTEN_SES_FROM'

# Comma-delimited field, if provided will send stylized HTML to them
#
# Example:
#   'user1@my.domain.org,user2@my.domain.org'
SES_TO_ENV_VAR = 'SHUUTEN_SES_TO'

# Optional
SES_REPLY_TO_ENV_VAR = 'SHUUTEN_SES_REPLY_TO'
SES_REGION_ENV_VAR = 'SHUUTEN_SES_REGION'

# Optional link to source code repo for the project
# SOURCE_CODE = getenv('SOURCE_CODE')

# Local time zone
LOCAL = 'LOCAL_TZ'
