#!/usr/bin/env python3
"""
Improved browser-based SVG to PNG conversion using Selenium.
Handles ChromeDriver installation and provides better error handling.
"""

import os
import sys
import tempfile
import subprocess
import requests
import zipfile
import stat
from pathlib import Path

def install_chromedriver():
    """Install ChromeDriver if not present"""
    
    # Check if chromedriver already exists
    chromedriver_path = "/usr/local/bin/chromedriver"
    if os.path.exists(chromedriver_path):
        return chromedriver_path
    
    # Try to find it in common locations
    common_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "./chromedriver",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    print("📥 ChromeDriver not found, attempting to download...")
    
    try:
        # Get Chrome version
        result = subprocess.run(["/usr/bin/chromium", "--version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("Could not get Chrome version")
        
        chrome_version = result.stdout.strip().split()[-1]
        major_version = chrome_version.split('.')[0]
        
        print(f"🔍 Detected Chrome version: {chrome_version}")
        
        # Download compatible ChromeDriver
        # Note: This is a simplified approach - in production you'd want proper version matching
        download_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
        
        response = requests.get(download_url)
        if response.status_code != 200:
            raise RuntimeError(f"Could not find ChromeDriver for Chrome {major_version}")
        
        driver_version = response.text.strip()
        driver_url = f"https://chromedriver.storage.googleapis.com/{driver_version}/chromedriver_linux64.zip"
        
        print(f"📥 Downloading ChromeDriver {driver_version}...")
        
        # Download and extract
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "chromedriver.zip")
            
            response = requests.get(driver_url)
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Move to local directory (since we might not have sudo)
            local_driver_path = "./chromedriver"
            subprocess.run(["cp", os.path.join(temp_dir, "chromedriver"), local_driver_path])
            os.chmod(local_driver_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            print(f"✅ ChromeDriver installed to {local_driver_path}")
            return local_driver_path
            
    except Exception as e:
        print(f"❌ Failed to install ChromeDriver: {e}")
        return None

def svg_to_png_browser_improved(svg_content: str, output_width: int = 2202, output_height: int = 1632) -> bytes:
    """
    Convert SVG to PNG using browser rendering with improved error handling.
    """
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        raise RuntimeError("Selenium not installed. Run: pip install selenium")
    
    # Install ChromeDriver if needed
    chromedriver_path = install_chromedriver()
    if not chromedriver_path:
        raise RuntimeError("Could not install or find ChromeDriver")
    
    # Create HTML wrapper for the SVG
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background: white; }}
            svg {{ display: block; width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        {svg_content}
    </body>
    </html>
    """
    
    # Set up Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Use new headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument(f"--window-size={output_width},{output_height}")
    
    # Find Chrome binary
    chrome_binary = "/usr/bin/chromium"
    if not os.path.exists(chrome_binary):
        possible_paths = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser"]
        for path in possible_paths:
            if os.path.exists(path):
                chrome_binary = path
                break
        else:
            raise RuntimeError("Chrome/Chromium not found")
    
    chrome_options.binary_location = chrome_binary
    
    # Set up service
    service = Service(chromedriver_path)
    
    driver = None
    temp_file = None
    
    try:
        print(f"🌐 Starting Chrome with binary: {chrome_binary}")
        print(f"🔧 Using ChromeDriver: {chromedriver_path}")
        
        # Create webdriver
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Create temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_file = f.name
        
        print(f"📄 Loading HTML file: {temp_file}")
        
        # Load the HTML file
        driver.get(f"file://{temp_file}")
        
        # Wait for SVG to load
        print("⏳ Waiting for SVG to load...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "svg"))
        )
        
        # Set window size to match desired output
        driver.set_window_size(output_width, output_height)
        
        print("📸 Taking screenshot...")
        # Take screenshot
        png_data = driver.get_screenshot_as_png()
        
        print(f"✅ Screenshot successful! Size: {len(png_data):,} bytes")
        return png_data
        
    finally:
        if driver:
            driver.quit()
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)

def test_browser_improved():
    """Test the improved browser-based approach"""
    
    # Read the SVG file
    svg_path = "maps/standard.svg"
    if not os.path.exists(svg_path):
        print(f"Error: {svg_path} not found")
        return
    
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        print("🌐 Testing improved browser-based SVG to PNG conversion...")
        png_bytes = svg_to_png_browser_improved(svg_content)
        
        # Save result
        output_path = "test_browser_improved.png"
        with open(output_path, 'wb') as f:
            f.write(png_bytes)
        
        print(f"✅ Improved browser approach successful!")
        print(f"📁 Output saved as: {output_path}")
        print(f"📏 Size: {len(png_bytes):,} bytes")
        
    except Exception as e:
        print(f"❌ Improved browser approach failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_browser_improved() 