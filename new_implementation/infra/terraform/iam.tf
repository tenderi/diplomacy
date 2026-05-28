# ---------------------------------------------------------------------------
# EC2 instance role: SSM agent + read SecureString parameters
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "diplomacy-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# Lets the SSM agent call ssm:* / ec2messages:* — required for Session
# Manager and aws ssm send-command.
resource "aws_iam_role_policy_attachment" "ec2_ssm_managed" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Read the diplomacy/* SecureStrings on boot and on service restart.
data "aws_iam_policy_document" "ec2_ssm_params" {
  statement {
    sid     = "ReadDiplomacyParameters"
    actions = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}/*"
    ]
  }
  statement {
    sid     = "DecryptDefaultSSMKey"
    actions = ["kms:Decrypt"]
    resources = [
      "arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alias/aws/ssm"
    ]
  }
}

resource "aws_iam_role_policy" "ec2_ssm_params" {
  name   = "read-diplomacy-ssm-params"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_ssm_params.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "diplomacy-ec2"
  role = aws_iam_role.ec2.name
}

# ---------------------------------------------------------------------------
# GitHub Actions OIDC: deploy role assumable from this repo's main branch
# ---------------------------------------------------------------------------

# One OIDC provider per AWS account. If you've configured GitHub Actions
# auth against another repo in the same account, import the existing
# provider instead of creating a second one:
#   terraform import aws_iam_openid_connect_provider.github \
#     arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_actions_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        for branch in var.github_deploy_branches :
        "repo:${var.github_owner}/${var.github_repo}:ref:refs/heads/${branch}"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "diplomacy-github-actions-deploy"
  description        = "Assumed by GitHub Actions on main-branch pushes to trigger SSM deploys."
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json
}

data "aws_iam_policy_document" "github_actions_deploy" {
  statement {
    sid       = "SendCommandToDiplomacyInstance"
    actions   = ["ssm:SendCommand"]
    resources = [
      aws_instance.diplomacy.arn,
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }
  statement {
    sid = "InspectCommandResults"
    actions = [
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
      "ssm:DescribeInstanceInformation",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name   = "deploy-via-ssm"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.github_actions_deploy.json
}
