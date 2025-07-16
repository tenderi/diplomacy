variable "github_ci_user_name" { default = "diplomacy-github-ci" }

resource "aws_iam_user" "github_ci" {
  name = var.github_ci_user_name
}

resource "aws_iam_access_key" "github_ci" {
  user = aws_iam_user.github_ci.name
}

resource "aws_iam_user_policy" "github_ci" {
  name = "diplomacy-github-ci-policy"
  user = aws_iam_user.github_ci.name
  policy = data.aws_iam_policy_document.github_ci.json
}

data "aws_iam_policy_document" "github_ci" {
  statement {
    actions = [
      "ecs:*",
      "ecr:*",
      "iam:PassRole",
      "rds:DescribeDBInstances",
      "cloudwatch:Describe*",
      "cloudwatch:Get*",
      "cloudwatch:List*"
    ]
    resources = ["*"]
  }
}

# Stub for custom app/task roles if needed
# resource "aws_iam_role" "app_task" { ... } 

# OIDC provider for GitHub Actions
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# IAM role for GitHub Actions OIDC (tenderi/diplomacy, main branch)
resource "aws_iam_role" "github_actions" {
  name = "github-actions-oidc"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:tenderi/diplomacy:ref:refs/heads/main"
          }
        }
      }
    ]
  })
  managed_policy_arns = [aws_iam_policy.github_actions_policy.arn]
} 