"""
Tests for execution context - ensuring code works when run as scripts/services,
not just when imported as modules.

These tests verify that the application can run in production-like contexts:
- As a script (python3 script.py)
- With different PYTHONPATH settings
- With different working directories
- As systemd would execute it
"""
import pytest
import subprocess
import sys
import os
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def project_root():
    """Get the project root directory"""
    return Path(__file__).parent.parent


@pytest.fixture
def src_dir(project_root):
    """Get the src directory"""
    return project_root / "src"


class TestTelegramBotExecutionContext:
    """Test that telegram_bot.py can be executed in different contexts"""
    
    def test_telegram_bot_runs_as_script_with_pythonpath(self, project_root, src_dir):
        """Test that server.telegram_bot.app can be imported with PYTHONPATH set (production-like)"""
        app_path = src_dir / "server" / "telegram_bot" / "app.py"

        if not app_path.exists():
            pytest.skip("server/telegram_bot/app.py not found")

        # Test with PYTHONPATH set (production-like)
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_dir)
        env['TELEGRAM_BOT_TOKEN'] = 'test_token'  # Prevent token errors

        # A plain import exercises exactly what `python -m server.telegram_bot`
        # does at import time - no synthetic spec-loading needed now that the
        # module lives inside the package proper.
        result = subprocess.run(
            [sys.executable, '-c',
             f'import sys; sys.path.insert(0, "{src_dir}"); '
             f'from server.telegram_bot.app import main; '
             f'print("Import successful")'],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should not fail with ImportError or ModuleNotFoundError
        # May fail with other errors (like missing token), but not import errors
        stderr = result.stderr or ""
        assert 'ImportError' not in stderr or 'cannot import name' not in stderr, \
            f"Import error when running as script: {stderr}"
        assert 'ModuleNotFoundError' not in stderr, \
            f"Module not found error: {stderr}"
        assert 'attempted relative import with no known parent package' not in stderr, \
            f"Relative import error: {stderr}"
        assert result.returncode == 0, \
            f"Plain import of server.telegram_bot.app failed: {stderr}"
    
    def test_telegram_bot_wrapper_script_works(self, project_root, src_dir):
        """Test that run_telegram_bot.py wrapper script works - verify package setup"""
        wrapper_path = src_dir / "server" / "run_telegram_bot.py"
        
        if not wrapper_path.exists():
            pytest.skip("run_telegram_bot.py not found")
        
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_dir)
        
        # Test that the wrapper's package setup logic works
        # This verifies the critical part: that server.server can be imported
        # with relative imports working when server package is registered
        test_code = f'''
import sys
sys.path.insert(0, "{src_dir}")
import os
os.chdir("{src_dir}/server")
import importlib.util
import importlib

# Simulate what the wrapper does - register server as a package
if 'server' not in sys.modules:
    server_pkg = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("server", "{src_dir}/server/__init__.py")
    )
    server_pkg.__path__ = ["{src_dir}/server"]
    server_pkg.__package__ = 'server'
    sys.modules['server'] = server_pkg

# Ensure server.telegram_bot package is importable
try:
    importlib.import_module('server.telegram_bot')
except ImportError:
    pass

# CRITICAL TEST: Import server.server - this should work with relative imports
# because server is registered as a package
try:
    server_module = importlib.import_module('server.server')
    # Verify it imported successfully
    assert hasattr(server_module, 'Server'), "Server class not found"
    print("✅ server.server imported successfully with relative imports working")
except Exception as e:
    error_msg = str(e)
    if "relative import" in error_msg or "no known parent package" in error_msg:
        print(f"❌ Relative import failed: {{error_msg}}")
        sys.exit(1)
    else:
        print(f"❌ Unexpected error: {{error_msg}}")
        sys.exit(1)

# Verify we can import from server.telegram_bot package
try:
    from server.telegram_bot.config import get_telegram_token
    print("✅ server.telegram_bot.config imported successfully")
except Exception as e:
    error_msg = str(e)
    if "is not a package" in error_msg:
        print(f"❌ Package conflict: {{error_msg}}")
        sys.exit(1)
    else:
        print(f"⚠️  Import warning (may be expected): {{error_msg}}")

print("✅ All wrapper script package setup verified")
'''
        
        result = subprocess.run(
            [sys.executable, '-c', test_code],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Check for critical package structure errors
        stderr = result.stderr or ""
        stdout = result.stdout or ""
        error_text = stderr + stdout
        
        critical_errors = [
            'attempted relative import with no known parent package',
            'is not a package',
            'server.telegram_bot.config.*is not a package'
        ]
        
        # Check for critical errors
        for error_type in critical_errors:
            if error_type in error_text:
                pytest.fail(
                    f"Critical package structure error: {error_type}\n"
                    f"Full output:\n{stdout}\n{stderr}"
                )
        
        # Should succeed
        assert result.returncode == 0, \
            f"Wrapper script package setup failed:\n{stdout}\n{stderr}"
        
        # Should have success messages
        assert '✅' in stdout, \
            f"Expected success messages not found:\n{stdout}\n{stderr}"
    
    def test_telegram_bot_imports_from_different_contexts(self, project_root, src_dir):
        """Test that imports work from different working directories"""
        app_path = src_dir / "server" / "telegram_bot" / "app.py"

        if not app_path.exists():
            pytest.skip("server/telegram_bot/app.py not found")

        # Test from project root
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_dir)

        result = subprocess.run(
            [sys.executable, '-c',
             'import sys; sys.path.insert(0, "' + str(src_dir) + '"); '
             'from server.telegram_bot.config import get_telegram_token; '
             'from server.telegram_bot.app import main; '
             'print("Import successful")'],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result.returncode == 0, \
            f"Import failed from project root: {result.stderr}"

        # Test from src/server directory (like systemd might)
        result2 = subprocess.run(
            [sys.executable, '-c',
             'import sys; sys.path.insert(0, "' + str(src_dir.parent) + '/src"); '
             'from server.telegram_bot.config import get_telegram_token; '
             'from server.telegram_bot.app import main; '
             'print("Import successful")'],
            cwd=str(src_dir / "server"),
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result2.returncode == 0, \
            f"Import failed from server directory: {result2.stderr}"


class TestPackageStructure:
    """Test that package structure doesn't conflict"""
    
    def test_no_shadowing_telegram_bot_module(self, src_dir: Path) -> None:
        """
        Guard against the package-shadowing bug regressing: server/telegram_bot.py
        must never exist alongside the server/telegram_bot/ package again, since the
        package always wins the import and silently makes the .py file dead code
        (this is exactly what broke `python -m server.telegram_bot` in production).
        """
        import sys
        import importlib.util

        telegram_bot_module_path = src_dir / "server" / "telegram_bot.py"
        assert not telegram_bot_module_path.exists(), (
            f"{telegram_bot_module_path} exists alongside the server/telegram_bot/ "
            "package - it would be silently shadowed and unimportable/unexecutable "
            "as `python -m server.telegram_bot`"
        )

        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        spec = importlib.util.find_spec("server.telegram_bot")
        assert spec is not None, "server.telegram_bot should resolve to the package"
        assert spec.submodule_search_locations, (
            "server.telegram_bot did not resolve to a package (empty "
            "submodule_search_locations) - shadowing may have regressed"
        )
    
    def test_relative_imports_work_in_production_context(self, src_dir):
        """Test that relative imports work when server.server is imported"""
        import sys
        sys.path.insert(0, str(src_dir))
        
        # This simulates what happens when telegram_bot.py imports things
        # that eventually import server.server (which uses relative imports)
        
        # Import server.server which uses relative imports
        from server.server import Server
        assert Server is not None
        
        # Import should work without "attempted relative import" errors
        server_instance = Server()
        assert server_instance is not None


class TestImportPaths:
    """Test imports work with different PYTHONPATH configurations"""
    
    def test_imports_with_production_pythonpath(self, src_dir):
        """Test imports work with production-like PYTHONPATH"""
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_dir)
        
        result = subprocess.run(
            [sys.executable, '-c',
             f'import sys; import os; sys.path.insert(0, os.environ.get("PYTHONPATH", "")); '
             'from server.telegram_bot.config import get_telegram_token; '
             'from server.server import Server; '
             'print("All imports successful")'],
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0, \
            f"Imports failed with production PYTHONPATH: {result.stderr}"
    
    def test_imports_without_explicit_pythonpath(self, project_root, src_dir):
        """Test imports work when PYTHONPATH is set via sys.path"""
        # Simulate what the wrapper script does
        result = subprocess.run(
            [sys.executable, '-c',
             f'import sys; sys.path.insert(0, "{src_dir}"); '
             'from server.telegram_bot.config import get_telegram_token; '
             'from server.server import Server; '
             'print("All imports successful")'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0, \
            f"Imports failed with sys.path setup: {result.stderr}"


class TestServiceExecution:
    """Test that code can execute in service-like contexts"""
    
    def test_telegram_bot_main_function_importable(self, src_dir):
        """Test that main() function can be imported and called"""
        import sys
        sys.path.insert(0, str(src_dir))

        # server/telegram_bot.py used to be shadowed by the server/telegram_bot/
        # package, which required loading it via spec_from_file_location as a
        # workaround. Now that its contents live at server/telegram_bot/app.py,
        # a plain import is the honest test of "does this module import cleanly".
        from server.telegram_bot.app import main

        # Check that main exists and is callable
        assert callable(main)
    
    def test_imports_dont_fail_in_service_context(self, src_dir):
        """Test that all necessary imports work when executed as a service"""
        import sys
        sys.path.insert(0, str(src_dir))
        
        # Simulate what happens when telegram_bot.py is loaded
        # These are all the imports that telegram_bot.py does
        try:
            from server.telegram_bot.config import TELEGRAM_TOKEN, API_URL, get_telegram_token
            from server.telegram_bot.api_client import api_post, api_get
            from server.telegram_bot.maps import send_game_map
            from server.telegram_bot.games import start
            from server.telegram_bot.orders import order
            from server.telegram_bot.messages import message
            from server.telegram_bot.ui import show_main_menu
            from server.telegram_bot.admin import start_demo_game
            from server.telegram_bot.notifications import fastapi_app
            from server.telegram_bot.channel_commands import link_channel
            from server.telegram_bot.channels import set_telegram_bot
        except ImportError as e:
            pytest.fail(f"Import failed in service context: {e}")

        # All imports should succeed
        assert True


class TestTelegramBotMainEntryPoint:
    """
    Regression tests for the telegram_bot.py / telegram_bot/ package shadowing bug.

    server/telegram_bot.py used to be shadowed by the server/telegram_bot/ package
    (same name, package wins on import), which made `python -m server.telegram_bot`
    - the production systemd ExecStart - fail with
    "'server.telegram_bot' is a package and cannot be directly executed".
    The fix moves the module's contents into server/telegram_bot/app.py and adds
    server/telegram_bot/__main__.py so the package itself is directly runnable.
    """

    def test_dunder_main_module_is_importable(self, src_dir: Path) -> None:
        """server.telegram_bot.__main__ must exist so `python -m server.telegram_bot` works."""
        import sys
        import importlib.util

        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        spec = importlib.util.find_spec("server.telegram_bot.__main__")
        assert spec is not None, (
            "server.telegram_bot.__main__ not found - "
            "`python -m server.telegram_bot` will fail to execute"
        )

    def test_python_dash_m_server_telegram_bot_smoke(self, project_root: Path, src_dir: Path) -> None:
        """
        `python -m server.telegram_bot` (the production ExecStart) must fail, if it fails
        at all, because TELEGRAM_BOT_TOKEN is unset - never because of the package/module
        shadowing bug this test guards against.
        """
        env = os.environ.copy()
        env["PYTHONPATH"] = str(src_dir)
        # Ensure the missing-token code path is what we exercise, not a real bot startup.
        env.pop("TELEGRAM_BOT_TOKEN", None)

        timed_out = False
        stderr = ""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "server.telegram_bot"],
                cwd=str(project_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            stderr = result.stderr or ""
        except subprocess.TimeoutExpired as exc:
            # A timeout only counts as a test failure if it's masking the import bug;
            # otherwise it's a separate (environment/network) concern outside this test's scope.
            timed_out = True
            raw_stderr = exc.stderr
            if isinstance(raw_stderr, bytes):
                stderr = raw_stderr.decode(errors="replace")
            else:
                stderr = raw_stderr or ""

        assert "No module named" not in stderr, (
            f"Shadowing bug regressed (module not found): {stderr}"
        )
        assert "cannot be directly executed" not in stderr, (
            f"Shadowing bug regressed (package not directly executable): {stderr}"
        )

        if timed_out:
            pytest.fail(
                "`python -m server.telegram_bot` did not exit within the timeout, but no "
                "import/shadowing error was seen either; investigate separately - "
                f"stderr tail: {stderr[-2000:]}"
            )

