"""
Tests for deployment scripts and infrastructure configuration.

These tests verify that:
- Deployment scripts generate correct configurations
- Systemd service files are valid
- Nginx configurations are correct
- Environment variable setup works
"""
import pytest
import re
import os
from pathlib import Path
import subprocess
import sys


@pytest.fixture
def terraform_dir():
    """Get the terraform directory"""
    project_root = Path(__file__).parent.parent
    return project_root / "infra" / "terraform"


@pytest.fixture
def user_data_path(terraform_dir):
    """Get the user_data.sh file path"""
    return terraform_dir / "user_data.sh"


class TestSystemdServiceConfiguration:
    """Test systemd service file generation"""
    
    def test_systemd_service_file_exists_in_user_data(self, user_data_path):
        """Test that systemd service configuration is in user_data.sh"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Should contain systemd service configuration
        assert '[Unit]' in content, "Systemd service [Unit] section not found"
        assert '[Service]' in content, "Systemd service [Service] section not found"
        assert '[Install]' in content, "Systemd service [Install] section not found"
    
    def test_diplomacy_service_has_correct_execstart(self, user_data_path):
        """Test that diplomacy service ExecStart is correct"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Find the ExecStart line for diplomacy service
        # Should use uvicorn to start the API
        execstart_match = re.search(
            r'ExecStart=([^\n]+)',
            content
        )
        
        if execstart_match:
            execstart = execstart_match.group(1)
            # Should use uvicorn or python3 with correct path
            assert 'uvicorn' in execstart or 'python3' in execstart, \
                f"ExecStart should use uvicorn or python3: {execstart}"
            assert 'src.server.api' in execstart or 'api' in execstart, \
                f"ExecStart should reference the API module: {execstart}"
    
    def test_telegram_bot_service_has_correct_execstart(self, user_data_path):
        """Test that telegram bot service ExecStart is correct"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Find ExecStart for diplomacy-bot service
        # Look for the section that defines diplomacy-bot.service
        bot_service_match = re.search(
            r'Description=Diplomacy Telegram Bot.*?ExecStart=([^\n]+)',
            content,
            re.DOTALL
        )
        
        if bot_service_match:
            execstart = bot_service_match.group(1).strip()
            
            # Should use python3 or the wrapper script
            assert 'python3' in execstart or 'run_telegram_bot.py' in execstart, \
                f"ExecStart should use python3 or wrapper script: {execstart}"
            
            # Should not use -m src.server.telegram_bot (which doesn't work)
            assert '-m src.server.telegram_bot' not in execstart, \
                "ExecStart should not use -m src.server.telegram_bot (doesn't work)"
            
            # Should reference the correct path
            assert 'telegram_bot' in execstart or 'run_telegram_bot' in execstart, \
                f"ExecStart should reference telegram bot: {execstart}"
    
    def test_telegram_bot_service_has_environment_file(self, user_data_path):
        """Test that telegram bot service has EnvironmentFile"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Find the diplomacy-bot service section
        bot_section = re.search(
            r'Description=Diplomacy Telegram Bot.*?\[Install\]',
            content,
            re.DOTALL
        )
        
        if bot_section:
            section = bot_section.group(0)
            # Should have EnvironmentFile
            assert 'EnvironmentFile' in section, \
                "Telegram bot service should have EnvironmentFile"
            assert '/opt/diplomacy/.env' in section, \
                "EnvironmentFile should point to /opt/diplomacy/.env"
    
    def test_services_have_correct_user(self, user_data_path):
        """Test that services run as the correct user"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Both services should run as 'diplomacy' user
        assert 'User=diplomacy' in content, \
            "Services should run as 'diplomacy' user"
    
    def test_services_have_restart_policy(self, user_data_path):
        """Test that services have restart policy"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Should have restart policy
        assert 'Restart=' in content, \
            "Services should have Restart policy"
        assert 'RestartSec=' in content, \
            "Services should have RestartSec"


class TestNginxConfiguration:
    """Test Nginx configuration"""
    
    def test_nginx_config_exists_in_user_data(self, user_data_path):
        """Test that Nginx configuration is in user_data.sh"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Should contain Nginx server block
        assert 'server {' in content, "Nginx server block not found"
        assert 'listen 80' in content, "Nginx should listen on port 80"
        assert 'proxy_pass' in content, "Nginx should have proxy_pass directives"
    
    def test_nginx_has_dashboard_location(self, user_data_path):
        """Test that Nginx has explicit dashboard location"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Should have explicit /dashboard location
        dashboard_match = re.search(
            r'location /dashboard\s*\{[^}]*proxy_pass',
            content,
            re.DOTALL
        )
        
        assert dashboard_match is not None, \
            "Nginx should have explicit /dashboard location block"
    
    def test_nginx_proxies_to_localhost_8000(self, user_data_path):
        """Test that Nginx proxies to localhost:8000"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        content = user_data_path.read_text()
        
        # Should proxy to localhost:8000
        assert 'proxy_pass http://localhost:8000' in content, \
            "Nginx should proxy to http://localhost:8000"


class TestDeployScript:
    """Test deploy_app.sh script"""
    
    def test_deploy_script_exists(self, terraform_dir):
        """Test that deploy_app.sh exists"""
        deploy_script = terraform_dir / "deploy_app.sh"
        
        if not deploy_script.exists():
            pytest.skip("deploy_app.sh not found")
        
        assert deploy_script.is_file(), "deploy_app.sh should be a file"
    
    def test_deploy_script_is_executable(self, terraform_dir):
        """Test that deploy_app.sh is executable"""
        deploy_script = terraform_dir / "deploy_app.sh"
        
        if not deploy_script.exists():
            pytest.skip("deploy_app.sh not found")
        
        # Check if file has execute permission
        assert os.access(deploy_script, os.X_OK), \
            "deploy_app.sh should be executable"
    
    def test_deploy_script_has_shebang(self, terraform_dir):
        """Test that deploy_app.sh has shebang"""
        deploy_script = terraform_dir / "deploy_app.sh"
        
        if not deploy_script.exists():
            pytest.skip("deploy_app.sh not found")
        
        content = deploy_script.read_text()
        assert content.startswith('#!/bin/bash'), \
            "deploy_app.sh should start with #!/bin/bash"
    
    def test_deploy_script_fixes_telegram_bot_service(self, terraform_dir):
        """Test that deploy_app.sh fixes telegram bot service configuration"""
        deploy_script = terraform_dir / "deploy_app.sh"
        
        if not deploy_script.exists():
            pytest.skip("deploy_app.sh not found")
        
        content = deploy_script.read_text()
        
        # Should contain code that fixes telegram bot service
        assert 'diplomacy-bot.service' in content, \
            "deploy_app.sh should configure diplomacy-bot.service"
        
        # Should use the wrapper script or correct path
        assert 'run_telegram_bot.py' in content or 'python3' in content, \
            "deploy_app.sh should reference run_telegram_bot.py or python3"
    
    def test_deploy_script_fixes_nginx_config(self, terraform_dir):
        """Test that deploy_app.sh fixes Nginx configuration"""
        deploy_script = terraform_dir / "deploy_app.sh"
        
        if not deploy_script.exists():
            pytest.skip("deploy_app.sh not found")
        
        content = deploy_script.read_text()
        
        # Should contain Nginx configuration
        assert 'nginx' in content.lower() or '/etc/nginx' in content, \
            "deploy_app.sh should configure Nginx"
        
        # Should have dashboard location
        assert 'location /dashboard' in content, \
            "deploy_app.sh should configure /dashboard location"


class TestWrapperScript:
    """Test the run_telegram_bot.py wrapper script"""
    
    def test_wrapper_script_exists(self, terraform_dir):
        """Test that run_telegram_bot.py exists"""
        project_root = terraform_dir.parent
        wrapper_script = project_root / "src" / "server" / "run_telegram_bot.py"
        
        if not wrapper_script.exists():
            pytest.skip("run_telegram_bot.py not found")
        
        assert wrapper_script.is_file(), "run_telegram_bot.py should exist"
    
    def test_wrapper_script_has_shebang(self, terraform_dir):
        """Test that wrapper script has shebang"""
        project_root = terraform_dir.parent
        wrapper_script = project_root / "src" / "server" / "run_telegram_bot.py"
        
        if not wrapper_script.exists():
            pytest.skip("run_telegram_bot.py not found")
        
        content = wrapper_script.read_text()
        assert content.startswith('#!/usr/bin/env python3') or content.startswith('#!/usr/bin/python3'), \
            "run_telegram_bot.py should have Python shebang"
    
    def test_wrapper_script_sets_pythonpath(self, terraform_dir):
        """Test that wrapper script sets PYTHONPATH correctly"""
        project_root = terraform_dir.parent
        wrapper_script = project_root / "src" / "server" / "run_telegram_bot.py"
        
        if not wrapper_script.exists():
            pytest.skip("run_telegram_bot.py not found")
        
        content = wrapper_script.read_text()
        
        # Should add src directory to sys.path
        assert 'sys.path.insert' in content or 'sys.path.append' in content, \
            "Wrapper script should modify sys.path"
        assert '/opt/diplomacy/src' in content or 'src_dir' in content, \
            "Wrapper script should add src directory to path"
    
    def test_wrapper_script_imports_telegram_bot_package(self, terraform_dir):
        """Test that wrapper script imports telegram_bot package correctly"""
        project_root = terraform_dir.parent
        wrapper_script = project_root / "src" / "server" / "run_telegram_bot.py"
        
        if not wrapper_script.exists():
            pytest.skip("run_telegram_bot.py not found")
        
        content = wrapper_script.read_text()
        
        # Should import server.telegram_bot package first
        assert 'server.telegram_bot' in content or 'importlib' in content, \
            "Wrapper script should import telegram_bot package or use importlib"


@pytest.mark.integration
class TestDeploymentScriptExecution:
    """Integration tests for deployment script execution"""
    
    def test_deploy_script_syntax_is_valid(self, terraform_dir):
        """Test that deploy_app.sh has valid bash syntax"""
        deploy_script = terraform_dir / "deploy_app.sh"
        
        if not deploy_script.exists():
            pytest.skip("deploy_app.sh not found")
        
        # Check bash syntax
        result = subprocess.run(
            ['bash', '-n', str(deploy_script)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, \
            f"deploy_app.sh has syntax errors: {result.stderr}"
    
    def test_user_data_script_syntax_is_valid(self, user_data_path):
        """Test that user_data.sh has valid bash syntax"""
        if not user_data_path.exists():
            pytest.skip("user_data.sh not found")
        
        # Check bash syntax
        result = subprocess.run(
            ['bash', '-n', str(user_data_path)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, \
            f"user_data.sh has syntax errors: {result.stderr}"

