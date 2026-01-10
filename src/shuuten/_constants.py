from logging import ERROR
from os import getenv


# Minimum level for library logs, to show up in CloudWatch
LOG_CFG = getenv('SHUUTEN_LOG_CFG')

# AWS Account Alias (name), can be optionally set in the environment
#
# If defined, will be used instead of making a call to `iam:ListAccountAliases`
# to retrieve the alias of the current AWS account.
AWS_ACCOUNT_NAME = getenv('AWS_ACCOUNT_NAME')

# AWS Region, should be automatically set for AWS Lambda functions
AWS_REGION = getenv('AWS_REGION', 'us-east-1')

# Minimum log level for messages sent to Slack
SLACK_LOG_LVL = getenv('SHUUTEN_SLACK_LOG_LVL', ERROR)

# Slack webhook
SLACK_WEBHOOK_URL = getenv('SHUUTEN_SLACK_WEBHOOK_URL')

# Optional link to source code repo for the project
SOURCE_CODE = getenv('SOURCE_CODE')

# (ECS Tasks) Optional link to the AWS log group
AWS_LOG_GROUP = getenv('AWS_LOG_GROUP')

# Local time zone
LOCAL_TZ = getenv('LOCAL_TZ', 'US/Eastern')

# SES outbound email address
# SES_IDENTITY = getenv('SES_IDENTITY')

# Comma delimited field, if provided will send stylized HTML to them
#
# Example:
#   'user1@my.domain.org,user2@my.domain.org'
# DEV_EMAILS = getenv('DEV_EMAILS')
