#!/usr/bin/env python3
"""
Local OSX Deployment Script for YAIL Server

This script:
1. Checks for virtual environment (creates if needed)
2. Activates virtual environment
3. Installs required dependencies
4. Verifies all system dependencies
5. Checks API key configuration
6. Validates network connectivity
7. Starts the YAIL server in foreground
8. Reports exact IP and port for client connection
9. Monitors server health and logs
"""

import os
import sys
import socket
import subprocess
import time
import logging
import signal
import json
import venv as venv_module
from pathlib import Path
from typing import Tuple, Optional, Dict, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SERVER_DIR = PROJECT_ROOT / "server"
VENV_DIR = SERVER_DIR / "penv"
ENV_FILE = SERVER_DIR / "env"
ENV_EXAMPLE = SCRIPT_DIR / "env.example"
REQUIREMENTS_FILE = SERVER_DIR / "requirements.txt"
YAIL_PORT = 5556
YAIL_HOST = "0.0.0.0"


class VirtualEnvironmentManager:
    """Manage Python virtual environment."""
    
    @staticmethod
    def venv_exists() -> bool:
        """Check if virtual environment exists."""
        return (VENV_DIR / "bin" / "python").exists()
    
    @staticmethod
    def create_venv() -> bool:
        """Create virtual environment."""
        try:
            logger.info(f"Creating virtual environment at {VENV_DIR}...")
            venv_module.create(str(VENV_DIR), with_pip=True)
            logger.info("✓ Virtual environment created")
            return True
        except Exception as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False
    
    @staticmethod
    def get_pip_executable() -> Path:
        """Get path to pip in virtual environment."""
        return VENV_DIR / "bin" / "pip"
    
    @staticmethod
    def get_python_executable() -> Path:
        """Get path to python in virtual environment."""
        return VENV_DIR / "bin" / "python"
    
    @staticmethod
    def install_requirements() -> bool:
        """Install requirements in virtual environment."""
        try:
            if not REQUIREMENTS_FILE.exists():
                logger.error(f"Requirements file not found: {REQUIREMENTS_FILE}")
                return False
            
            logger.info("Installing dependencies...")
            pip_exe = VirtualEnvironmentManager.get_pip_executable()
            
            # Upgrade pip first
            logger.info("Upgrading pip...")
            result = subprocess.run(
                [str(pip_exe), "install", "--upgrade", "pip"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.warning(f"pip upgrade had issues: {result.stderr}")
            
            # Install requirements
            logger.info("Installing requirements from requirements.txt...")
            result = subprocess.run(
                [str(pip_exe), "install", "-r", str(REQUIREMENTS_FILE)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install requirements: {result.stderr}")
                return False
            
            logger.info("✓ Dependencies installed successfully")
            return True
        
        except subprocess.TimeoutExpired:
            logger.error("Installation timed out")
            return False
        except Exception as e:
            logger.error(f"Error installing requirements: {e}")
            return False
    
    @staticmethod
    def setup_venv() -> bool:
        """Setup or activate virtual environment."""
        logger.info("\n" + "=" * 60)
        logger.info("Virtual Environment Setup")
        logger.info("=" * 60 + "\n")
        
        if VirtualEnvironmentManager.venv_exists():
            logger.info(f"✓ Virtual environment found at {VENV_DIR}")
        else:
            logger.info(f"Virtual environment not found at {VENV_DIR}")
            if not VirtualEnvironmentManager.create_venv():
                return False
        
        # Install requirements
        if not VirtualEnvironmentManager.install_requirements():
            return False
        
        logger.info("")
        return True


class HealthChecker:
    """Check system health and dependencies."""
    
    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.checks_passed = 0
        self.checks_total = 0
    
    def check(self, name: str, condition: bool, error_msg: str = "", warning: bool = False) -> bool:
        """
        Perform a check and track results.
        
        Args:
            name: Name of the check
            condition: Result of the check
            error_msg: Error message if check fails
            warning: If True, treat as warning instead of error
        
        Returns:
            True if check passed, False otherwise
        """
        self.checks_total += 1
        
        if condition:
            logger.info(f"✓ {name}")
            self.checks_passed += 1
            return True
        else:
            msg = f"✗ {name}"
            if error_msg:
                msg += f": {error_msg}"
            
            if warning:
                logger.warning(msg)
                self.warnings.append(msg)
            else:
                logger.error(msg)
                self.issues.append(msg)
            
            return condition
    
    def summary(self) -> bool:
        """Print summary and return True if all critical checks passed."""
        logger.info("\n" + "=" * 60)
        logger.info(f"Health Check Summary: {self.checks_passed}/{self.checks_total} passed")
        logger.info("=" * 60)
        
        if self.warnings:
            logger.warning(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  {warning}")
        
        if self.issues:
            logger.error(f"\nCritical Issues ({len(self.issues)}):")
            for issue in self.issues:
                logger.error(f"  {issue}")
            return False
        
        logger.info("\n✓ All critical checks passed!")
        return True


def check_python_version() -> bool:
    """Check if Python 3.8+ is available."""
    version = sys.version_info
    return version.major >= 3 and version.minor >= 8


def check_python_modules() -> Tuple[bool, List[str]]:
    """Check if required Python modules are available in venv."""
    required_modules = [
        'PIL',  # Pillow
        'requests',
        'dotenv',
        'tqdm',
        'fastcore',
        'duckduckgo_search',
    ]
    
    python_exe = VirtualEnvironmentManager.get_python_executable()
    missing = []
    
    for module in required_modules:
        try:
            result = subprocess.run(
                [str(python_exe), "-c", f"import {module}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                missing.append(module)
        except Exception:
            missing.append(module)
    
    return len(missing) == 0, missing


def check_env_file() -> Tuple[bool, Optional[Dict[str, str]]]:
    """Check if env file exists and is readable."""
    if not ENV_FILE.exists():
        logger.warning(f"No env file found at {ENV_FILE}")
        logger.info(f"Creating from example: {ENV_EXAMPLE}")
        
        if ENV_EXAMPLE.exists():
            with open(ENV_EXAMPLE, 'r') as f:
                example_content = f.read()
            with open(ENV_FILE, 'w') as f:
                f.write(example_content)
            logger.info(f"Created {ENV_FILE}")
        else:
            return False, None
    
    # Parse env file
    env_vars = {}
    try:
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip().strip("'\"")
        return True, env_vars
    except Exception as e:
        logger.error(f"Error reading env file: {e}")
        return False, None


def check_api_keys(env_vars: Dict[str, str]) -> Tuple[bool, str]:
    """Check if at least one API key is configured."""
    openai_key = env_vars.get('OPENAI_API_KEY', '').strip()
    gemini_key = env_vars.get('GEMINI_API_KEY', '').strip()
    
    gen_model = env_vars.get('GEN_MODEL', 'dall-e-3').lower()
    
    if 'gemini' in gen_model:
        if gemini_key and gemini_key != 'your_gemini_api_key_here_if_needed':
            return True, "Gemini API key configured"
        else:
            return False, "Gemini model selected but no valid API key"
    else:
        if openai_key and openai_key != 'your_openai_api_key_here':
            return True, "OpenAI API key configured"
        else:
            return False, "No valid OpenAI API key found"


def check_network() -> Tuple[bool, str]:
    """Check network connectivity and get local IP."""
    try:
        # Try to connect to a public DNS to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return True, local_ip
    except Exception as e:
        logger.warning(f"Could not determine IP via socket: {e}")
        return False, "127.0.0.1"


def check_port_available(port: int) -> bool:
    """Check if port is available."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.close()
        return True
    except OSError:
        return False


def check_requirements_file() -> bool:
    """Check if requirements.txt exists."""
    return REQUIREMENTS_FILE.exists()


def check_server_files() -> bool:
    """Check if all required server files exist."""
    required_files = [
        SERVER_DIR / "yail.py",
        SERVER_DIR / "yail_gen.py",
        SERVER_DIR / "yail_camera.py",
        SERVER_DIR / "yail_server_state.py",
        SERVER_DIR / "yail_image_converter.py",
        SERVER_DIR / "yail_image_streamer.py",
        SERVER_DIR / "yail_command_parser.py",
        SERVER_DIR / "yail_client_handler.py",
    ]
    
    missing = [f for f in required_files if not f.exists()]
    return len(missing) == 0, missing


def run_health_checks() -> Tuple[bool, str, int]:
    """Run all health checks."""
    checker = HealthChecker()
    
    logger.info("\n" + "=" * 60)
    logger.info("YAIL Local OSX Deployment - Health Checks")
    logger.info("=" * 60 + "\n")
    
    # Python version
    checker.check("Python 3.8+", check_python_version(), 
                  f"Current version: {sys.version_info.major}.{sys.version_info.minor}")
    
    # Python modules
    modules_ok, missing = check_python_modules()
    if not modules_ok:
        checker.check("Python modules", False, 
                     f"Missing: {', '.join(missing)}")
    else:
        checker.check("Python modules", True)
    
    # Requirements file
    checker.check("requirements.txt exists", check_requirements_file(),
                 f"Not found at {REQUIREMENTS_FILE}")
    
    # Server files
    files_ok, missing_files = check_server_files()
    if not files_ok:
        checker.check("Server files", False,
                     f"Missing: {', '.join(str(f.name) for f in missing_files)}")
    else:
        checker.check("Server files", True)
    
    # Env file
    env_ok, env_vars = check_env_file()
    checker.check("Environment file", env_ok)
    
    # API keys
    if env_ok and env_vars:
        api_ok, api_msg = check_api_keys(env_vars)
        checker.check("API configuration", api_ok, api_msg)
    else:
        checker.check("API configuration", False, "Could not read env file")
        env_vars = {}
    
    # Network
    net_ok, local_ip = check_network()
    checker.check("Network connectivity", net_ok, f"Local IP: {local_ip}")
    
    # Port availability
    port_ok = check_port_available(YAIL_PORT)
    checker.check(f"Port {YAIL_PORT} available", port_ok,
                 f"Port may already be in use")
    
    # Print summary
    all_ok = checker.summary()
    
    return all_ok, local_ip, checker.checks_passed


def start_server(local_ip: str) -> Optional[subprocess.Popen]:
    """
    Start the YAIL server in foreground using venv Python.
    
    Args:
        local_ip: Local IP address to report
    
    Returns:
        Process object or None if failed
    """
    logger.info("\n" + "=" * 60)
    logger.info("Starting YAIL Server")
    logger.info("=" * 60 + "\n")
    
    # Prepare environment
    env = os.environ.copy()
    
    # Load env file variables
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env[key.strip()] = value.strip().strip("'\"")
    
    # Use venv Python
    python_exe = VirtualEnvironmentManager.get_python_executable()
    
    # Build command
    cmd = [
        str(python_exe),
        str(SERVER_DIR / "yail.py"),
        "--loglevel", "INFO",
    ]
    
    try:
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info(f"Working directory: {SERVER_DIR}")
        logger.info(f"Using Python: {python_exe}")
        logger.info("")
        
        # Start server
        process = subprocess.Popen(
            cmd,
            cwd=str(SERVER_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Give server time to start
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            logger.error("Server failed to start")
            return None
        
        logger.info("✓ Server started successfully\n")
        
        # Print connection info
        logger.info("=" * 60)
        logger.info("YAIL Server Ready for Connections")
        logger.info("=" * 60)
        logger.info(f"Host: {local_ip}")
        logger.info(f"Port: {YAIL_PORT}")
        logger.info(f"URL: {local_ip}:{YAIL_PORT}")
        logger.info("=" * 60)
        logger.info("\nServer is running in foreground.")
        logger.info("Press Ctrl+C to stop the server.\n")
        logger.info("=" * 60 + "\n")
        
        return process
    
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return None


def monitor_server(process: subprocess.Popen) -> None:
    """
    Monitor server output and handle signals.
    
    Args:
        process: Server process
    """
    def signal_handler(sig, frame):
        logger.info("\n\nShutting down server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Server did not stop gracefully, killing...")
            process.kill()
        logger.info("Server stopped.")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Monitor output
    try:
        for line in process.stdout:
            print(line, end='')
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        logger.error(f"Error monitoring server: {e}")
    finally:
        process.wait()


def main():
    """Main deployment function."""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " " * 58 + "║")
    logger.info("║" + "  YAIL Server - Local OSX Deployment".center(58) + "║")
    logger.info("║" + " " * 58 + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("")
    
    # Setup virtual environment first
    if not VirtualEnvironmentManager.setup_venv():
        logger.error("\n✗ Deployment aborted: Failed to setup virtual environment.")
        sys.exit(1)
    
    # Run health checks
    all_ok, local_ip, checks_passed = run_health_checks()
    
    if not all_ok:
        logger.error("\n✗ Deployment aborted due to critical issues.")
        logger.error("Please fix the issues above and try again.")
        sys.exit(1)
    
    # Start server
    process = start_server(local_ip)
    
    if process is None:
        logger.error("✗ Failed to start server")
        sys.exit(1)
    
    # Monitor server
    monitor_server(process)


if __name__ == "__main__":
    main()
