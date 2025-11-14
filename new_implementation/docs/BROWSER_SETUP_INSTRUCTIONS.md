# Browser-Based SVG Rendering Setup Instructions

This document provides instructions for setting up browser-based SVG to PNG conversion using Selenium and Chrome/Chromium.

## Why Browser-Based Rendering?

The original `cairosvg` library has issues with CSS processing, leading to incorrect colors in the rendered maps. Browser-based rendering uses a real browser engine (Chrome/Chromium) which handles CSS perfectly, just like the old implementation did.

## Local Development Setup

### 1. Install Selenium

```bash
# In your virtual environment
source venv/bin/activate
pip install selenium
```

### 2. Install Chrome/Chromium

**On Ubuntu/Debian:**
```bash
# Install Chromium (lightweight alternative)
sudo apt-get update
sudo apt-get install -y chromium-browser

# OR install Google Chrome (full version)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable
```

**On Arch Linux:**
```bash
# Install Chromium
sudo pacman -S chromium

# OR install Google Chrome from AUR
yay -S google-chrome
```

**On macOS:**
```bash
# Install Chrome via Homebrew
brew install --cask google-chrome

# OR install Chromium
brew install --cask chromium
```

### 3. Install ChromeDriver

**Automatic (recommended):**
The `map_browser.py` module will attempt to download ChromeDriver automatically.

**Manual:**
```bash
# Check your Chrome version
google-chrome --version  # or chromium --version

# Download matching ChromeDriver from:
# https://chromedriver.chromium.org/downloads

# Extract and place in PATH
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```

## EC2 Production Setup

### 1. Deploy the Browser Dependencies

The deployment includes an automated setup script. After deploying your code:

```bash
# SSH into your EC2 instance
ssh -i ~/.ssh/helgeKeyPair.pem ubuntu@YOUR_EC2_IP

# Run the browser dependencies installation script
sudo /opt/diplomacy/install_browser_deps.sh
```

### 2. Update Requirements

The `requirements.txt` already includes `selenium`. Make sure to install it:

```bash
# On the EC2 instance
cd /opt/diplomacy
sudo -u diplomacy pip install -r requirements.txt
```

### 3. Restart Services

```bash
sudo systemctl restart diplomacy-bot
sudo systemctl restart diplomacy-api  # if applicable
```

## Usage

### Automatic (Recommended)

The system will automatically choose the best rendering method:

```python
from src.engine.map_browser import render_board_png_auto

# This will use browser rendering if available, fall back to cairosvg
png_bytes = render_board_png_auto("maps/standard.svg", units={})
```

### Manual Browser Rendering

```python
from src.engine.map_browser import render_board_png_browser

try:
    png_bytes = render_board_png_browser("maps/standard.svg", units={})
    print("Browser rendering successful!")
except Exception as e:
    print(f"Browser rendering failed: {e}")
```

### Check Availability

```python
from src.engine.map_browser import is_browser_rendering_available

if is_browser_rendering_available():
    print("✅ Browser rendering is available")
else:
    print("❌ Browser rendering not available, will use cairosvg fallback")
```

## Integration with Telegram Bot

The telegram bot can be updated to use browser rendering:

```python
# In telegram_bot.py
try:
    from src.engine.map_browser import render_board_png_auto
    # Use browser rendering with fallback
    img_bytes = render_board_png_auto(svg_path, units)
except ImportError:
    # Fallback to original method
    from src.engine.map import Map
    img_bytes = Map.render_board_png(svg_path, units)
```

## Troubleshooting

### Common Issues

1. **ChromeDriver version mismatch:**
   ```bash
   # Check versions match
   google-chrome --version
   chromedriver --version
   ```

2. **Permission issues:**
   ```bash
   # Make sure ChromeDriver is executable
   sudo chmod +x /usr/local/bin/chromedriver
   ```

3. **Missing dependencies on headless server:**
   ```bash
   # Install additional packages
   sudo apt-get install -y fonts-liberation libasound2 libatk-bridge2.0-0 \
       libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 \
       libgtk-3-0 libnspr4 libnss3 libxcomposite1 libxdamage1 libxfixes3 \
       libxkbcommon0 libxrandr2 xdg-utils
   ```

4. **Selenium import errors:**
   ```bash
   # Reinstall selenium
   pip uninstall selenium
   pip install selenium
   ```

### Debugging

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run your rendering code
```

Check Chrome logs:
```bash
# Run Chrome manually to see errors
google-chrome --headless --disable-gpu --dump-dom about:blank
```

## Performance Considerations

- Browser rendering is slower than cairosvg but produces correct colors
- Consider caching rendered maps to improve performance
- The browser starts up for each rendering call (could be optimized with persistent sessions)

## Security Notes

- Browser rendering requires more system resources
- Chrome runs in headless mode with security restrictions
- Consider resource limits in production environments

## Files Modified

- `requirements.txt` - Added selenium dependency
- `src/engine/map_browser.py` - New browser-based rendering module  
- `install_browser_deps.sh` - EC2 setup script
- `infra/terraform/single-ec2/deploy_fixes.sh` - Updated deployment script

## Testing

Test the setup:

```bash
# Test browser rendering locally
cd new_implementation
source venv/bin/activate
python -c "
from src.engine.map_browser import render_board_png_auto
png_bytes = render_board_png_auto('maps/standard.svg', {})
print(f'✅ Rendered {len(png_bytes):,} bytes')
"
``` 