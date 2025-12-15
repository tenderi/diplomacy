# Telegram Bot Troubleshooting Guide

## Quick Diagnosis

Run the diagnostic script on the server:
```bash
ssh -i YOUR_KEY.pem ubuntu@YOUR_SERVER_IP
sudo /opt/diplomacy/infra/scripts/diagnose_bot.sh
```

Or if the script isn't on the server yet:
```bash
ssh -i YOUR_KEY.pem ubuntu@YOUR_SERVER_IP
sudo bash -c 'cd /opt/diplomacy && curl -s https://raw.githubusercontent.com/YOUR_REPO/main/infra/scripts/diagnose_bot.sh | bash'
```

## Common Issues and Fixes

### 1. Bot Service Not Running

**Check status:**
```bash
sudo systemctl status diplomacy-bot
```

**If stopped, start it:**
```bash
sudo systemctl start diplomacy-bot
sudo systemctl enable diplomacy-bot  # Enable auto-start on boot
```

**View logs:**
```bash
sudo journalctl -u diplomacy-bot -n 50 --no-pager
sudo journalctl -u diplomacy-bot -f  # Follow logs in real-time
```

### 2. Missing Telegram Bot Token

**Check if token is set:**
```bash
sudo -u diplomacy grep TELEGRAM_BOT_TOKEN /opt/diplomacy/.env
```

**If missing, add it:**
```bash
sudo -u diplomacy bash -c 'echo "TELEGRAM_BOT_TOKEN=your_token_here" >> /opt/diplomacy/.env'
sudo systemctl restart diplomacy-bot
```

### 3. API Not Responding

The bot waits for the API to be healthy before starting.

**Check API status:**
```bash
sudo systemctl status diplomacy
curl http://localhost:8000/health
```

**If API is down:**
```bash
sudo systemctl start diplomacy
sudo systemctl restart diplomacy-bot  # Restart bot after API is up
```

### 4. Import Errors

**Check for Python import errors:**
```bash
sudo journalctl -u diplomacy-bot | grep -i "import\|module\|no module"
```

**Common fixes:**
- Ensure dependencies are installed: `sudo -u diplomacy pip3 install --user -r /opt/diplomacy/requirements.txt`
- Check Python path: `sudo -u diplomacy python3 -c "import sys; print(sys.path)"`

### 5. Permission Errors

**Check file ownership:**
```bash
ls -la /opt/diplomacy/src/server/run_telegram_bot.py
```

**Fix ownership if needed:**
```bash
sudo chown -R diplomacy:diplomacy /opt/diplomacy
```

### 6. Sudo Errors (Dashboard)

These errors don't prevent the bot from working, but they clutter logs.

**Fix sudoers configuration:**
```bash
sudo /opt/diplomacy/infra/scripts/fix_sudoers.sh
```

Or manually:
```bash
sudo visudo -f /etc/sudoers.d/diplomacy-systemctl
# Ensure each command is on its own line
```

## Manual Bot Test

Test the bot script directly:
```bash
sudo -u diplomacy bash -c 'cd /opt/diplomacy && /usr/bin/python3 src/server/run_telegram_bot.py'
```

This will show any immediate errors.

## Restart Everything

If all else fails:
```bash
sudo systemctl restart diplomacy
sudo systemctl restart diplomacy-bot
sleep 5
sudo systemctl status diplomacy-bot
```

## Check Bot is Responding

Once the bot is running, test it:
1. Open Telegram
2. Find your bot
3. Send `/start` command
4. Bot should respond

If it doesn't respond:
- Check logs: `sudo journalctl -u diplomacy-bot -f`
- Verify token is correct
- Check if bot is actually running: `sudo systemctl is-active diplomacy-bot`

