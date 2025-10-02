#!/usr/bin/env python3
"""
Browser-based SVG to PNG conversion using Selenium.
This should handle CSS much better than cairosvg.
"""

import os
import sys
import base64
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def svg_to_png_browser(svg_content: str, output_width: int = 2202, output_height: int = 1632) -> bytes:
    """
    Convert SVG to PNG using browser rendering (Selenium + Chrome).
    This should handle CSS much better than cairosvg.
    """
    
    # Create HTML wrapper for the SVG
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; }}
            svg {{ display: block; }}
        </style>
    </head>
    <body>
        {svg_content}
    </body>
    </html>
    """
    
    # Set up Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"--window-size={output_width},{output_height}")
    
    # Try to find Chrome/Chromium
    possible_chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser", 
        "/usr/bin/chromium",
        "/snap/bin/chromium",
    ]
    
    chrome_path = None
    for path in possible_chrome_paths:
        if os.path.exists(path):
            chrome_path = path
            break
    
    if not chrome_path:
        raise RuntimeError("Chrome/Chromium not found. Please install google-chrome or chromium-browser.")
    
    chrome_options.binary_location = chrome_path
    
    driver = None
    try:
        # Create webdriver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Create temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = f.name
        
        try:
            # Load the HTML file
            driver.get(f"file://{html_file}")
            
            # Wait for SVG to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "svg"))
            )
            
            # Set window size to match desired output
            driver.set_window_size(output_width, output_height)
            
            # Take screenshot
            png_data = driver.get_screenshot_as_png()
            
            return png_data
            
        finally:
            # Clean up temp file
            os.unlink(html_file)
            
    finally:
        if driver:
            driver.quit()

def test_browser_approach():
    """Test the browser-based approach"""
    
    # Read the SVG file
    svg_path = "maps/standard.svg"
    if not os.path.exists(svg_path):
        print(f"Error: {svg_path} not found")
        return
    
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        print("🌐 Testing browser-based SVG to PNG conversion...")
        png_bytes = svg_to_png_browser(svg_content)
        
        # Save result
        output_path = "test_browser_approach.png"
        with open(output_path, 'wb') as f:
            f.write(png_bytes)
        
        print(f"✅ Browser approach successful!")
        print(f"📁 Output saved as: {output_path}")
        print(f"📏 Size: {len(png_bytes):,} bytes")
        
    except Exception as e:
        print(f"❌ Browser approach failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_browser_approach() 