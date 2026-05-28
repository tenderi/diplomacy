# Secrets live in SSM Parameter Store as SecureStrings. They are managed
# *outside* of Terraform — the values are put there by the operator with:
#
#   aws ssm put-parameter --name /diplomacy/telegram_bot_token \
#     --type SecureString --value '<token>' --region eu-north-1
#
# Terraform only references the parameter names so the EC2 instance role
# can read them, and so that user_data and the deploy workflow know where
# to look. Storing the values in Terraform would put them in tfstate.

locals {
  ssm_prefix = "/diplomacy"

  ssm_parameter_names = {
    telegram_bot_token = "${local.ssm_prefix}/telegram_bot_token"
    db_password        = "${local.ssm_prefix}/db_password"
    jwt_secret         = "${local.ssm_prefix}/jwt_secret"
    admin_token        = "${local.ssm_prefix}/admin_token"
    bot_secret         = "${local.ssm_prefix}/bot_secret"
  }
}

data "aws_caller_identity" "current" {}
