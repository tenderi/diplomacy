#!/usr/bin/env python3
"""
Alternative map rendering using browser-based SVG to PNG conversion.
This should handle CSS much better than cairosvg.
"""

import os
import tempfile
import subprocess
from typing import Dict, Optional


def render_board_png_browser(svg_path: str, units: Dict, output_path: str = None) -> bytes:
    """
    Render the diplomacy map using browser-based conversion.
    
    :param svg_path: Path to the SVG file
    :param units: Dict of units by power {power: ["A PAR", "F LON", ...]}
    :param output_path: Optional path to save the PNG
    :return: PNG bytes
    """
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        raise RuntimeError("Selenium not installed. Browser-based rendering unavailable.")
    
    if not os.path.exists(svg_path):
        raise ValueError(f"SVG file not found: {svg_path}")
    
    # Read the SVG content
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()
    
    # Apply minimal fixes to SVG (remove black rectangle)
    svg_content = _fix_svg_for_browser(svg_content, units)
    
    # Create HTML wrapper
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background: white; }}
            svg {{ display: block; width: 100vw; height: 100vh; }}
        </style>
    </head>
    <body>
        {svg_content}
    </body>
    </html>
    """
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=2202,1632")
    
    # Find Chrome binary
    chrome_binary = _find_chrome_binary()
    if not chrome_binary:
        raise RuntimeError("Chrome/Chromium not found")
    
    chrome_options.binary_location = chrome_binary
    
    # Find or install ChromeDriver
    chromedriver_path = _find_chromedriver()
    if not chromedriver_path:
        raise RuntimeError("ChromeDriver not found")
    
    driver = None
    temp_file = None
    
    try:
        # Create webdriver
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Create temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_file = f.name
        
        # Load the HTML file
        driver.get(f"file://{temp_file}")
        
        # Wait for SVG to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "svg"))
        )
        
        # Take screenshot
        png_data = driver.get_screenshot_as_png()
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(png_data)
        
        return png_data
        
    finally:
        if driver:
            driver.quit()
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


def _fix_svg_for_browser(svg_content: str, units: Dict) -> str:
    """Apply minimal fixes to SVG for browser rendering"""
    
    import re
    
    # Remove the problematic black rectangle
    svg_content = re.sub(
        r'<rect fill="black" height="1360" width="1835" x="195" y="170"/>',
        '<!-- Removed problematic black background rectangle -->',
        svg_content
    )
    
    # TODO: Add units to the map
    # For now, just return the fixed SVG
    
    return svg_content


def _find_chrome_binary() -> Optional[str]:
    """Find Chrome/Chromium binary"""
    
    possible_paths = [
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None


def _find_chromedriver() -> Optional[str]:
    """Find ChromeDriver binary"""
    
    possible_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "./chromedriver",
        "/opt/chromedriver/chromedriver",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None


def is_browser_rendering_available() -> bool:
    """Check if browser-based rendering is available"""
    
    try:
        import selenium
        return _find_chrome_binary() is not None and _find_chromedriver() is not None
    except ImportError:
        return False


# Fallback to cairosvg if browser rendering is not available
def render_board_png_fallback(svg_path: str, units: Dict, output_path: str = None) -> bytes:
    """Fallback to cairosvg rendering"""
    
    import cairosvg
    
    if not os.path.exists(svg_path):
        raise ValueError(f"SVG file not found: {svg_path}")
    
    # Use cairosvg as fallback
    png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=2202, output_height=1632)
    
    if png_bytes is None:
        raise ValueError("cairosvg.svg2png returned None")
    
    if output_path:
        with open(output_path, 'wb') as f:
            f.write(png_bytes)
    
    return png_bytes


def render_board_png_auto(svg_path: str, units: Dict, output_path: str = None) -> bytes:
    """
    Automatically choose the best rendering method available.
    Prefers browser-based rendering, falls back to cairosvg.
    """
    
    if is_browser_rendering_available():
        try:
            return render_board_png_browser(svg_path, units, output_path)
        except Exception as e:
            print(f"Browser rendering failed, falling back to cairosvg: {e}")
    
    return render_board_png_fallback(svg_path, units, output_path) 