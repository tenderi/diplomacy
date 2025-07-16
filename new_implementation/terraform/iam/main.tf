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