# Map Rendering Test Summary

All test scripts are now configured to save outputs to the `test_maps/` directory with timestamp prefixes for easy chronological ordering.

## Available Test Scripts

### 1. `simple_test.py` - Basic Functionality Test
**Purpose:** Quick test to verify basic map rendering works  
**Usage:** `python simple_test.py`  
**Output:** `test_maps/YYYYMMDD_HHMMSS_simple_test_output.png`  
**What it tests:**
- Basic SVG to PNG conversion
- File size check
- Quick pixel sampling to detect if map is mostly black

### 2. `check_map_quality.py` - Comprehensive Quality Analysis
**Purpose:** Detailed analysis of both cairosvg and browser rendering  
**Usage:** `python check_map_quality.py`  
**Output:** 
- `test_maps/YYYYMMDD_HHMMSS_current_rendering.png` (cairosvg)
- `test_maps/YYYYMMDD_HHMMSS_browser_rendering.png` (if browser available)

**What it tests:**
- Color distribution analysis (black %, white %, dark %)
- Average brightness calculation
- Color variance (how colorful the map is)
- Quality assessment with pass/fail criteria

### 3. `test_map_rendering.py` - Pytest Test Suite
**Purpose:** Formal pytest tests for CI/CD integration  
**Usage:** `python -m pytest test_map_rendering.py -v -s`  
**Output:**
- `test_maps/YYYYMMDD_HHMMSS_cairosvg_output.png`
- `test_maps/YYYYMMDD_HHMMSS_browser_output.png`
- `test_maps/YYYYMMDD_HHMMSS_comparison_cairosvg.png`
- `test_maps/YYYYMMDD_HHMMSS_comparison_browser.png`

**What it tests:**
- Formal assertions for map quality
- Black pixel percentage < 60% (main CSS issue test)
- Color variance > 1000 (colorfulness test)
- Average brightness > 80 (darkness test)
- Comparison between rendering methods

### 4. `test_map_generation.py` - Scenario Testing
**Purpose:** Test different game scenarios and unit configurations  
**Usage:** `python test_map_generation.py --scenario empty`  
**Output:** `test_maps/YYYYMMDD_HHMMSS_empty_map.png` (etc.)

**Available scenarios:**
- `empty` - Clean board with no units
- `starting` - Standard 1901 starting positions
- `midgame` - Typical mid-game state
- `crowded` - Many units on the board
- `fleets` - Fleet-heavy scenario
- `armies` - Army-heavy scenario

## Quality Assessment Criteria

### ✅ PASS Criteria (Map is working correctly):
- **Black pixels:** < 60% of total pixels
- **Color variance:** > 1000 (indicates good color diversity)
- **Average brightness:** > 80 (not too dark)
- **File size:** > 1KB (not empty/corrupted)

### ❌ FAIL Criteria (CSS rendering issue detected):
- **Black pixels:** > 60% (indicates CSS classes not rendering properly)
- **Color variance:** < 1000 (map is mostly one color)
- **Average brightness:** < 80 (map is too dark)

## Expected Results

### With CSS Issue (Current Problem):
- Black pixels: ~80-90%
- Color variance: ~500-800
- Average brightness: ~30-50
- Visual: Mostly black map with some light areas

### Without CSS Issue (Goal):
- Black pixels: ~15-25%
- Color variance: ~2000-4000
- Average brightness: ~120-150
- Visual: Colorful map with proper country colors

## Running Tests

### Quick Test:
```bash
cd new_implementation
source venv/bin/activate
python simple_test.py
```

### Full Quality Analysis:
```bash
cd new_implementation
source venv/bin/activate
python check_map_quality.py
```

### Pytest Suite:
```bash
cd new_implementation
source venv/bin/activate
python -m pytest test_map_rendering.py::test_cairosvg_map_rendering_quality -v -s
```

### Scenario Testing:
```bash
cd new_implementation
source venv/bin/activate
python test_map_generation.py --scenario empty
```

## File Naming Convention

All test outputs use the format: `YYYYMMDD_HHMMSS_description.png`

Examples:
- `20250723_154500_simple_test_output.png`
- `20250723_154501_current_rendering.png`
- `20250723_154502_browser_rendering.png`

This ensures chronological ordering and easy identification of test runs.

## Dependencies

All tests require:
- `PIL` (Pillow) - Image processing
- `numpy` - Color analysis
- `cairosvg` - SVG to PNG conversion

Browser tests additionally require:
- `selenium` - Browser automation
- Chrome/Chromium browser
- ChromeDriver

## Next Steps

1. Run the tests manually to verify current map quality
2. Check if the black percentage is > 60% (indicating CSS issue)
3. If CSS issue confirmed, deploy browser-based rendering solution
4. Re-run tests to verify improvement 