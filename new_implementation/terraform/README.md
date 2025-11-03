# Single EC2 Instance Deployment (Ubuntu 22.04)

This is the **cheapest possible** deployment option for the Diplomacy game server. Everything runs on a single `t3.micro` instance with **Ubuntu 22.04 LTS**:

- **PostgreSQL database** (latest version, local)
- **FastAPI server** (Python with latest packages)
- **Telegram bot** (Python)
- **Nginx reverse proxy**

## Cost: ~$9/month or FREE (AWS Free Tier)

- EC2 t3.micro: $8.50/month (**FREE** for first 12 months)
- EBS 10GB: $1/month (**FREE** 30GB for first 12 months)
- **Total: $9.50/month** or **FREE** with AWS Free Tier

## Prerequisites

1. **AWS Account** with Free Tier eligibility (if you want free hosting)
2. **AWS CLI** configured with your credentials
3. **Terraform** installed (>= 1.3.0)
4. **EC2 Key Pair** created in AWS Console
5. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)

## Quick Start

### 1. Configure Variables
```bash
# Copy the example file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

Required variables:
- `telegram_bot_token`: Get from @BotFather on Telegram
- `key_name`: Your EC2 Key Pair name (create in AWS Console)
- `allowed_ssh_cidr`: Your public IP for SSH access (get from ipconfig.me)

### 2. Deploy Infrastructure
```bash
# Initialize Terraform
terraform init

# Plan the deployment
terraform plan

# Deploy (takes ~5 minutes)
terraform apply
```

### 3. Deploy Application Code
After Terraform completes, you'll get the instance IP. Deploy your code:

```bash
# Get the instance IP from Terraform output
INSTANCE_IP=$(terraform output -raw public_ip)

# Copy your application code
scp -i ~/.ssh/YOUR_KEY.pem -r ../../new_implementation ubuntu@$INSTANCE_IP:/tmp/

# SSH to the instance
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP

# On the instance, copy code to the application directory
sudo cp -r /tmp/new_implementation/* /opt/diplomacy/new_implementation/
sudo chown -R diplomacy:diplomacy /opt/diplomacy/new_implementation

# Start the diplomacy service
sudo systemctl start diplomacy

# Check status
sudo /opt/diplomacy/status.sh
```

### 4. Access Your Application
- **API**: `http://YOUR_INSTANCE_IP:8000`
- **Via Nginx**: `http://YOUR_INSTANCE_IP`
- **Docs**: `http://YOUR_INSTANCE_IP:8000/docs`
- **Dashboard**: `http://YOUR_INSTANCE_IP/dashboard` (deploy with `./deploy_dashboard.sh`)

## Management Commands

### Check Status
```bash
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo /opt/diplomacy/status.sh"
```

### View Logs
```bash
# Application logs
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo journalctl -u diplomacy -f"

# Setup logs
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo tail -f /var/log/user-data.log"
```

### Restart Services
```bash
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo systemctl restart diplomacy"
```

### Update Application
```bash
# Use the built-in deployment script
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo -u diplomacy /opt/diplomacy/deploy.sh"
```

### Deploy Dashboard
```bash
# Deploy the dashboard (HTML, CSS, JS files)
./deploy_dashboard.sh
```

The dashboard provides a web interface for monitoring and managing the bot:
- **Service Status**: View and restart services
- **Logs Viewer**: View real-time logs from both services
- **Database Viewer**: Browse database tables and view statistics

Access the dashboard at: `http://YOUR_INSTANCE_IP/dashboard`

## Architecture

```
┌─────────────────────────────────────────┐
│           EC2 t3.micro                  │
│  ┌───────────────────────────────────┐  │
│  │         Nginx :80                 │  │ ← Optional proxy
│  │    (proxies to :8000)            │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │    FastAPI + Telegram Bot :8000  │  │ ← Your app
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │      PostgreSQL :5432             │  │ ← Local database
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
              │
    ┌─────────────────┐
    │   Internet      │
    └─────────────────┘
```

## Security Notes

1. **Restrict SSH access**: Set `allowed_ssh_cidr` to your IP (`YOUR.IP.ADDRESS/32`)
2. **Use strong passwords**: Change default database password
3. **Keep updated**: Regularly update the instance (`sudo yum update -y`)
4. **Consider SSL**: Add Let's Encrypt certificate for HTTPS

## Troubleshooting

### Instance won't start?
```bash
# Check user-data logs
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo cat /var/log/user-data.log"
```

### Database connection issues?
```bash
# Test database connection
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo -u diplomacy psql -h localhost -U diplomacy -d diplomacy -c 'SELECT version();'"
```

### Application won't start?
```bash
# Check application logs
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo journalctl -u diplomacy -n 50"

# Check if all files are present
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@$INSTANCE_IP "sudo ls -la /opt/diplomacy/new_implementation/src/"
```

## Scaling Up Later

If your application grows, you can easily migrate to the full ECS setup:
1. Take a database backup
2. Deploy the full Terraform configuration
3. Restore database to RDS
4. Update DNS to point to the new load balancer

## Cost Optimization Tips

1. **Use Free Tier**: First 12 months are free
2. **No Elastic IP**: Saves $3.65/month (IP changes on restart)
3. **Stop when not needed**: Stop the instance when not in use
4. **Monitor usage**: Use CloudWatch to track resource usage
5. **Reserved Instances**: If running long-term, Reserved Instances save 75%

## Cleanup

To destroy all resources:
```bash
terraform destroy
```

**Note**: This will delete everything, including your database! 