"""
QuantSight Backend Launcher
Smart bootstrap that ensures Python environment is ready on first run.
Downloads embedded Python and dependencies automatically.
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.12.0"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "QuantSight"
PYTHON_DIR = APP_DIR / "python"
VENV_DIR = APP_DIR / "venv"
BACKEND_DIR = Path(__file__).parent

def log(msg):
    print(f"[QuantSight] {msg}")

def download_file(url, dest):
    """Download file with progress"""
    log(f"Downloading {url.split('/')[-1]}...")
    urllib.request.urlretrieve(url, dest)
    log("Download complete!")

def setup_embedded_python():
    """Download and setup embedded Python if not present"""
    python_exe = PYTHON_DIR / "python.exe"
    
    if python_exe.exists():
        return python_exe
    
    log("Setting up Python environment (first-time setup)...")
    APP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Download embedded Python
    zip_path = APP_DIR / "python.zip"
    download_file(PYTHON_EMBED_URL, zip_path)
    
    # Extract
    log("Extracting Python...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(PYTHON_DIR)
    zip_path.unlink()
    
    # Enable pip by modifying pth file
    pth_file = PYTHON_DIR / f"python{PYTHON_VERSION.replace('.', '')[:2]}._pth"
    if pth_file.exists():
        content = pth_file.read_text()
        if "#import site" in content:
            content = content.replace("#import site", "import site")
            pth_file.write_text(content)
            log("Enabled site module in Python configuration")
        
        # Verify the change worked
        if "import site" not in pth_file.read_text() or "#import site" in pth_file.read_text():
            log("WARNING: Failed to enable site module - pip may not work!")
    
    # Download get-pip.py and install pip
    log("Installing pip...")
    getpip_path = APP_DIR / "get-pip.py"
    download_file("https://bootstrap.pypa.io/get-pip.py", getpip_path)
    subprocess.run([str(python_exe), str(getpip_path)], check=True)
    getpip_path.unlink()
    
    return python_exe

def install_requirements(python_exe):
    """Install Python dependencies"""
    requirements_file = BACKEND_DIR / "requirements.txt"
    marker_file = APP_DIR / ".deps_installed"
    
    # Check if already installed
    if marker_file.exists():
        req_mtime = requirements_file.stat().st_mtime if requirements_file.exists() else 0
        marker_mtime = marker_file.stat().st_mtime
        if marker_mtime > req_mtime:
            return  # Already up to date
    
    log("Installing dependencies (this may take a few minutes on first run)...")
    
    # Install from requirements.txt
    if requirements_file.exists():
        subprocess.run([
            str(python_exe), "-m", "pip", "install", 
            "-r", str(requirements_file)
        ], check=True)
    else:
        # Fallback: install core packages directly
        packages = [
            "numpy", "pandas", "scipy", "scikit-learn",
            "fastapi", "uvicorn[standard]", "pydantic",
            "nba_api", "requests", "beautifulsoup4",
            "pybreaker", "psutil", "aiohttp"
        ]
        subprocess.run([
            str(python_exe), "-m", "pip", "install", 
            *packages
        ], check=True)
    
    # Mark as installed
    marker_file.write_text("installed")
    log("Dependencies ready!")

def start_server(python_exe):
    """Start the FastAPI backend server"""
    server_script = BACKEND_DIR / "server.py"
    
    log("Starting backend server...")
    
    # Run server
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    
    subprocess.run([
        str(python_exe), "-m", "uvicorn",
        "server:app",
        "--host", "127.0.0.1",
        "--port", "5000"
    ], cwd=str(BACKEND_DIR), env=env)

def main():
    try:
        # Setup Python
        python_exe = setup_embedded_python()
        
        # Install dependencies
        install_requirements(python_exe)
        
        # Start server
        start_server(python_exe)
        
    except Exception as e:
        log(f"Error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
