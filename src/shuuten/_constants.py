from os import getenv


# AWS Account Alias (name), can be optionally set in the environment
#
# If defined, will be used instead of making a call to `iam:ListAccountAliases`
# to retrieve the alias of the current AWS account.
AWS_ACCOUNT_NAME = getenv('AWS_ACCOUNT_NAME')

# SSL Cert bundle (optional)
CA_BUNDLE_ENV_VAR = 'SHUUTEN_CA_BUNDLE'

# Local time zone
LOCAL = 'LOCAL_TZ'
