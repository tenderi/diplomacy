# Telegram Bot Troubleshooting (production)

For the EC2 host. The two systemd units are **`diplomacy-api`** and **`diplomacy-bot`**.
Get a shell with SSM (no SSH key needed):

```bash
aws ssm start-session --target $(terraform output -raw instance_id) --region eu-north-1
```

## Quick diagnosis

```bash
sudo /opt/diplomacy/new_implementation/infra/scripts/diagnose_bot.sh
```

## 1. Service not running

```bash
sudo systemctl status diplomacy-bot
sudo systemctl start diplomacy-bot && sudo systemctl enable diplomacy-bot
sudo journalctl -u diplomacy-bot -n 50 --no-pager
sudo journalctl -u diplomacy-bot -f              # follow
```

## 2. Missing or wrong bot token

```bash
sudo grep TELEGRAM_BOT_TOKEN /opt/diplomacy/.env
```

The token comes from SSM, not from the repo. To rotate it:

```bash
aws ssm put-parameter --name /diplomacy/telegram_bot_token --type SecureString \
  --value '<new-token>' --overwrite --region eu-north-1
# then on the instance:
sudo bash /opt/diplomacy/new_implementation/infra/scripts/refresh-env.sh
sudo systemctl restart diplomacy-bot
```

## 3. API not responding

The bot waits for the API to be healthy before it starts.

```bash
sudo systemctl status diplomacy-api
curl http://localhost:8000/health
sudo systemctl start diplomacy-api && sudo systemctl restart diplomacy-bot
```

## 4. Import errors

```bash
sudo journalctl -u diplomacy-bot | grep -i "no module\|importerror"
```

Almost always a missing `PYTHONPATH=src` or an incomplete
`pip install -r requirements.txt`. The unit file sets both — check it hasn't drifted from
`infra/terraform/user_data.sh`.

## 5. Permission errors

```bash
ls -la /opt/diplomacy/new_implementation/src/server/run_telegram_bot.py
sudo chown -R diplomacy:diplomacy /opt/diplomacy
```

## 6. Sudo errors in the dashboard

Noisy but harmless to the bot itself:

```bash
sudo /opt/diplomacy/new_implementation/infra/scripts/fix_sudoers.sh
```

## Restart everything

```bash
sudo systemctl restart diplomacy-api diplomacy-bot
sleep 5 && sudo systemctl status diplomacy-bot
```

Then send `/start` to the bot in Telegram. If it stays silent, tail
`journalctl -u diplomacy-bot -f` while sending the command — the request either doesn't
arrive (token/network) or fails inside a handler (which will show in the log).
