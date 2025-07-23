#!/bin/bash
# Install browser dependencies for SVG rendering on EC2 Ubuntu instance

set -e

echo "=== Installing Browser Dependencies for SVG Rendering ==="

# Update package list
echo "📦 Updating package list..."
sudo apt-get update

# Install Google Chrome
echo "🌐 Installing Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    # Add Google Chrome repository
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    
    # Update and install Chrome
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
    
    echo "✅ Google Chrome installed"
else
    echo "✅ Google Chrome already installed"
fi

# Install ChromeDriver
echo "🔧 Installing ChromeDriver..."
if ! command -v chromedriver &> /dev/null; then
    # Get Chrome version
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1)
    echo "🔍 Detected Chrome version: $CHROME_VERSION"
    
    # Get compatible ChromeDriver version
    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION")
    echo "📥 Downloading ChromeDriver version: $DRIVER_VERSION"
    
    # Download and install ChromeDriver
    wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$DRIVER_VERSION/chromedriver_linux64.zip"
    sudo unzip /tmp/chromedriver.zip -d /usr/local/bin/
    sudo chmod +x /usr/local/bin/chromedriver
    rm /tmp/chromedriver.zip
    
    echo "✅ ChromeDriver installed to /usr/local/bin/chromedriver"
else
    echo "✅ ChromeDriver already installed"
fi

# Install additional dependencies for headless Chrome
echo "📦 Installing additional dependencies..."
sudo apt-get install -y \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils

# Verify installation
echo "🧪 Verifying installation..."
google-chrome --version
chromedriver --version

echo "✅ Browser dependencies installation complete!"
echo ""
echo "📋 Installation Summary:"
echo "  - Google Chrome: $(google-chrome --version | awk '{print $3}')"
echo "  - ChromeDriver: $(chromedriver --version | awk '{print $2}')"
echo "  - Location: /usr/local/bin/chromedriver"
echo ""
echo "🚀 Browser-based SVG rendering is now available!" 