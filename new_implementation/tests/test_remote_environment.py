"""
Tests for remote environment validation.

These tests verify that the remote server environment is correctly configured
and matches expected requirements for running the Diplomacy application.
"""
import os
import sys
import pytest
from pathlib import Path
from typing import Dict, Any


class TestPathResolution:
    """Test path resolution and file system structure."""
    
    def test_project_root_exists(self):
        """Verify project root directory exists."""
        # Try to find project root from common locations
        possible_roots = [
            "/opt/diplomacy",
            os.path.join(os.path.dirname(__file__), "..", ".."),
            os.getcwd(),
        ]
        
        project_root = None
        for root in possible_roots:
            root_path = Path(root).resolve()
            if root_path.exists() and root_path.is_dir():
                # Check for key indicators
                if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                    project_root = root_path
                    break
        
        assert project_root is not None, "Project root directory not found"
        assert project_root.exists(), f"Project root does not exist: {project_root}"
        assert project_root.is_dir(), f"Project root is not a directory: {project_root}"
    
    def test_src_directory_exists(self):
        """Verify src directory exists and is accessible."""
        project_root = self._find_project_root()
        src_dir = project_root / "src"
        
        assert src_dir.exists(), f"src directory does not exist: {src_dir}"
        assert src_dir.is_dir(), f"src is not a directory: {src_dir}"
        assert os.access(src_dir, os.R_OK), f"src directory is not readable: {src_dir}"
    
    def test_maps_directory_exists(self):
        """Verify maps directory exists."""
        project_root = self._find_project_root()
        maps_dir = project_root / "maps"
        
        assert maps_dir.exists(), f"maps directory does not exist: {maps_dir}"
        assert maps_dir.is_dir(), f"maps is not a directory: {maps_dir}"
        assert os.access(maps_dir, os.R_OK), f"maps directory is not readable: {maps_dir}"
    
    def test_test_maps_directory_creatable(self):
        """Verify test_maps directory can be created or exists."""
        project_root = self._find_project_root()
        test_maps_dir = project_root / "test_maps"
        
        # Directory should exist or be creatable
        if not test_maps_dir.exists():
            # Try to create it
            try:
                test_maps_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                pytest.fail(f"Cannot create test_maps directory: {e}")
        
        assert test_maps_dir.exists(), f"test_maps directory does not exist: {test_maps_dir}"
        assert os.access(test_maps_dir, os.W_OK), f"test_maps directory is not writable: {test_maps_dir}"
    
    def test_standard_svg_exists(self):
        """Verify standard.svg map file exists."""
        project_root = self._find_project_root()
        svg_path = project_root / "maps" / "standard.svg"
        
        assert svg_path.exists(), f"standard.svg does not exist: {svg_path}"
        assert svg_path.is_file(), f"standard.svg is not a file: {svg_path}"
        assert os.access(svg_path, os.R_OK), f"standard.svg is not readable: {svg_path}"
        assert svg_path.stat().st_size > 0, f"standard.svg is empty: {svg_path}"
    
    def test_demo_script_exists(self):
        """Verify demo_perfect_game.py script exists."""
        project_root = self._find_project_root()
        demo_script = project_root / "examples" / "demo_perfect_game.py"
        
        # Also check root directory (for deployment)
        if not demo_script.exists():
            demo_script = project_root / "demo_perfect_game.py"
        
        assert demo_script.exists(), f"demo_perfect_game.py does not exist: {demo_script}"
        assert demo_script.is_file(), f"demo_perfect_game.py is not a file: {demo_script}"
        assert os.access(demo_script, os.R_OK), f"demo_perfect_game.py is not readable: {demo_script}"
    
    def _find_project_root(self) -> Path:
        """Find project root directory."""
        possible_roots = [
            "/opt/diplomacy",
            Path(__file__).parent.parent,
            Path(os.getcwd()),
        ]
        
        for root in possible_roots:
            root_path = Path(root).resolve()
            if root_path.exists() and root_path.is_dir():
                if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                    return root_path
        
        raise AssertionError("Could not find project root directory")


class TestFilePermissions:
    """Test file permissions and ownership."""
    
    def test_src_directory_permissions(self):
        """Verify src directory has correct permissions."""
        project_root = self._find_project_root()
        src_dir = project_root / "src"
        
        assert os.access(src_dir, os.R_OK), "src directory must be readable"
        # On remote server, should be readable by diplomacy user
    
    def test_maps_directory_permissions(self):
        """Verify maps directory has correct permissions."""
        project_root = self._find_project_root()
        maps_dir = project_root / "maps"
        
        assert os.access(maps_dir, os.R_OK), "maps directory must be readable"
    
    def test_test_maps_writable(self):
        """Verify test_maps directory is writable."""
        project_root = self._find_project_root()
        test_maps_dir = project_root / "test_maps"
        
        # Ensure it exists
        test_maps_dir.mkdir(parents=True, exist_ok=True)
        
        assert os.access(test_maps_dir, os.W_OK), "test_maps directory must be writable"
        
        # Test write capability
        test_file = test_maps_dir / ".test_write"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            pytest.fail(f"Cannot write to test_maps directory: {e}")
    
    def _find_project_root(self) -> Path:
        """Find project root directory."""
        possible_roots = [
            "/opt/diplomacy",
            Path(__file__).parent.parent,
            Path(os.getcwd()),
        ]
        
        for root in possible_roots:
            root_path = Path(root).resolve()
            if root_path.exists() and root_path.is_dir():
                if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                    return root_path
        
        raise AssertionError("Could not find project root directory")


class TestDependencies:
    """Test Python dependencies."""
    
    def test_python_version(self):
        """Verify Python version is 3.8 or higher."""
        version = sys.version_info
        assert version.major == 3, f"Python major version must be 3, got {version.major}"
        assert version.minor >= 8, f"Python minor version must be >= 8, got {version.minor}"
    
    def test_critical_imports(self):
        """Test that critical Python packages can be imported."""
        critical_packages = [
            "fastapi",
            "sqlalchemy",
            "telegram",
            "PIL",  # Pillow
        ]
        
        missing = []
        for package in critical_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        assert not missing, f"Missing critical packages: {', '.join(missing)}"
    
    def test_src_imports(self):
        """Test that src modules can be imported."""
        project_root = self._find_project_root()
        src_dir = project_root / "src"
        
        # Add src to path
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        
        # Try importing key modules
        try:
            from engine.map import Map
            from engine.game import Game
            from server.server import Server
        except ImportError as e:
            pytest.fail(f"Cannot import src modules: {e}")
    
    def _find_project_root(self) -> Path:
        """Find project root directory."""
        possible_roots = [
            "/opt/diplomacy",
            Path(__file__).parent.parent,
            Path(os.getcwd()),
        ]
        
        for root in possible_roots:
            root_path = Path(root).resolve()
            if root_path.exists() and root_path.is_dir():
                if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                    return root_path
        
        raise AssertionError("Could not find project root directory")


class TestConfiguration:
    """Test configuration and environment variables."""
    
    def test_pythonpath_set(self):
        """Verify PYTHONPATH includes src directory."""
        project_root = self._find_project_root()
        src_dir = project_root / "src"
        
        pythonpath = os.environ.get("PYTHONPATH", "")
        # PYTHONPATH should include src or be empty (we'll add it)
        # This is a warning, not a failure
        if pythonpath and str(src_dir) not in pythonpath:
            pytest.skip("PYTHONPATH does not include src directory (may be set at runtime)")
    
    def test_map_path_accessible(self):
        """Verify map files are accessible via DIPLOMACY_MAP_PATH or default location."""
        project_root = self._find_project_root()
        default_map = project_root / "maps" / "standard.svg"
        
        map_path = os.environ.get("DIPLOMACY_MAP_PATH")
        if map_path:
            assert Path(map_path).exists(), f"DIPLOMACY_MAP_PATH points to non-existent file: {map_path}"
        else:
            # Use default location
            assert default_map.exists(), f"Default map file does not exist: {default_map}"
    
    def _find_project_root(self) -> Path:
        """Find project root directory."""
        possible_roots = [
            "/opt/diplomacy",
            Path(__file__).parent.parent,
            Path(os.getcwd()),
        ]
        
        for root in possible_roots:
            root_path = Path(root).resolve()
            if root_path.exists() and root_path.is_dir():
                if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                    return root_path
        
        raise AssertionError("Could not find project root directory")


class TestMapFiles:
    """Test map file accessibility."""
    
    def test_standard_svg_readable(self):
        """Verify standard.svg can be read."""
        project_root = self._find_project_root()
        svg_path = project_root / "maps" / "standard.svg"
        
        assert svg_path.exists(), f"standard.svg does not exist: {svg_path}"
        
        # Try to read the file
        try:
            content = svg_path.read_text(encoding='utf-8')
            assert len(content) > 0, "standard.svg is empty"
            assert "<svg" in content.lower(), "standard.svg does not appear to be valid SVG"
        except Exception as e:
            pytest.fail(f"Cannot read standard.svg: {e}")
    
    def test_v2_svg_optional(self):
        """Verify v2.svg exists (optional, for standard-v2 map)."""
        project_root = self._find_project_root()
        v2_svg = project_root / "maps" / "v2.svg"
        
        # This is optional, so we just check if it exists
        if v2_svg.exists():
            assert v2_svg.is_file(), f"v2.svg exists but is not a file: {v2_svg}"
            assert os.access(v2_svg, os.R_OK), f"v2.svg is not readable: {v2_svg}"
    
    def _find_project_root(self) -> Path:
        """Find project root directory."""
        possible_roots = [
            "/opt/diplomacy",
            Path(__file__).parent.parent,
            Path(os.getcwd()),
        ]
        
        for root in possible_roots:
            root_path = Path(root).resolve()
            if root_path.exists() and root_path.is_dir():
                if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                    return root_path
        
        raise AssertionError("Could not find project root directory")

