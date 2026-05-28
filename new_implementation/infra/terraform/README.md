# Diplomacy infrastructure (single EC2, eu-north-1)

Cheapest viable production setup: one `t3.micro` EC2 in the default VPC running PostgreSQL + FastAPI + the Telegram bot. Free for 12 months on the AWS free tier, ~$10–15/month after.

```
┌─────────────────────── eu-north-1 ──────────────────────┐
│                                                         │
│  Default VPC (free)                                     │
│  └─ Public subnet                                       │
│     └─ Security group: 80 ← world, 22 ← your IP (opt)   │
│        └─ EC2 t3.micro · Ubuntu 24.04 · 10 GB gp3       │
│           ├─ nginx (port 80)                            │
│           ├─ uvicorn  → server._api_module:app (8000)   │
│           ├─ python -m server.telegram_bot              │
│           └─ postgresql-16 (localhost only)             │
│                                                         │
│  SSM Parameter Store /diplomacy/*  (SecureString)       │
│    ├─ telegram_bot_token                                │
│    ├─ db_password           (auto-generated on first    │
│    ├─ jwt_secret             boot if not set)           │
│    ├─ admin_token                                       │
│    └─ bot_secret                                        │
│                                                         │
│  IAM role  diplomacy-ec2          ← attached to EC2     │
│  IAM role  diplomacy-github-actions-deploy ← OIDC,      │
│             assumable from refs/heads/main, perms:      │
│             ssm:SendCommand to the instance only        │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- AWS account with permission to create IAM, EC2, SSM, S3, Budgets.
- AWS CLI configured locally (`aws configure` or SSO profile).
- Terraform **>= 1.10** (uses S3 native state locking — no DynamoDB).

## One-time bootstrap

The S3 backend bucket must exist before `terraform init`. Two commands:

```bash
aws s3api create-bucket \
  --bucket diplomacy-tfstate-tenderi \
  --region eu-north-1 \
  --create-bucket-configuration LocationConstraint=eu-north-1

aws s3api put-bucket-versioning \
  --bucket diplomacy-tfstate-tenderi \
  --versioning-configuration Status=Enabled
```

If you want a different bucket name, edit `versions.tf` before running these.

## Put the secrets in SSM

The terraform does **not** manage secret values — only the EC2 instance's permission to read them. Set them once before the first apply:

```bash
read -srp 'Telegram bot token: ' TOKEN && echo
aws ssm put-parameter \
  --name /diplomacy/telegram_bot_token \
  --type SecureString --value "$TOKEN" \
  --region eu-north-1

# Optional — the bootstrap script will auto-generate db_password if missing,
# but if you'd rather pick your own:
aws ssm put-parameter --name /diplomacy/db_password \
  --type SecureString --value "$(openssl rand -base64 32)" --region eu-north-1

# Optional — only needed if you don't want the dev defaults from the source
# code (those refuse to start a production server anyway).
aws ssm put-parameter --name /diplomacy/jwt_secret \
  --type SecureString --value "$(openssl rand -hex 32)" --region eu-north-1
aws ssm put-parameter --name /diplomacy/admin_token \
  --type SecureString --value "$(openssl rand -hex 32)" --region eu-north-1
aws ssm put-parameter --name /diplomacy/bot_secret \
  --type SecureString --value "$(openssl rand -hex 32)" --region eu-north-1
```

## First apply

```bash
cd new_implementation/infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars to set (at minimum) budget_alert_email.

terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

First apply takes ~3 minutes for AWS resources, then the instance spends another ~5–8 minutes running user_data (apt install, pip install, alembic upgrade). Watch:

```bash
INSTANCE=$(terraform output -raw instance_id)
aws ssm start-session --target "$INSTANCE" --region eu-north-1
# inside the session:
sudo tail -f /var/log/diplomacy-bootstrap.log
```

When bootstrap finishes, `curl http://$(terraform output -raw public_ip)/health` should return 200.

## Wire up CI deploys

Take the OIDC role ARN from the apply output and set it as a repo variable:

```bash
ROLE=$(terraform output -raw github_actions_deploy_role_arn)
gh variable set AWS_DEPLOY_ROLE_ARN --body "$ROLE"
gh variable set AWS_REGION --body "eu-north-1"
```

From the next push to `main` that turns the **Test Suite** workflow green, the **Deploy** workflow will run and ship the commit via `aws ssm send-command`. No SSH key on the runner, no static AWS credentials.

## Day-to-day operations

| Task | Command |
|---|---|
| Open a shell on the instance | `aws ssm start-session --target $(terraform output -raw instance_id) --region eu-north-1` |
| Deploy manually | GitHub Actions → Deploy → Run workflow, or `git push` to `main` |
| Deploy a specific commit | Run-workflow with `ref: <sha-or-tag>` |
| Tail logs | `journalctl -u diplomacy-api -f` / `journalctl -u diplomacy-bot -f` (in SSM session) |
| Rotate Telegram token | `aws ssm put-parameter --name /diplomacy/telegram_bot_token --type SecureString --value '<new>' --overwrite`; then in SSM session: `sudo systemctl restart diplomacy-bot` |
| Rotate DB password | put the new value in SSM, then re-run user_data: `sudo cloud-init clean && sudo reboot` (or run the relevant subset by hand) |
| Stop the instance (save money) | `aws ec2 stop-instances --instance-ids $(terraform output -raw instance_id) --region eu-north-1` |
| Resume | `aws ec2 start-instances ...` — public IP will change (no Elastic IP) |
| Destroy everything | `terraform destroy` |

## Costs (eu-north-1, after the 12-month free tier)

| Resource | Monthly |
|---|---|
| 1× t3.micro EC2 (730 hrs) | ~$8.50 |
| 10 GB gp3 EBS | ~$0.95 |
| 100 GB outbound bandwidth | free tier, then $0.09/GB |
| S3 state bucket | < $0.05 |
| AWS Budgets | free |
| **Estimated total** | **~$10** |

For the first 12 months: ~$0 if traffic stays under 100 GB outbound.

## What's intentionally missing

- **No Elastic IP** — saves $3.65/month. If you reboot or stop+start, the public IP changes. If/when you add a domain, point an A record at the EIP or use Route 53 with a small TTL.
- **No HTTPS** — TLS deferred until you bring a domain. Add later with `certbot --nginx`.
- **No RDS** — Postgres is on the EC2 box. RDS doubles the cost and adds free-tier accounting. Restore a recent EBS snapshot if you ever need DR.
- **No autoscaling / load balancer** — solo instance is plenty for a turn-based game. Reach for ALB + ASG when you actually need multiple workers.
- **No CloudWatch alarms beyond Budgets** — start simple. Add later when you have something to alarm on.
