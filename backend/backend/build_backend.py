"""
Build script for QuantSight Backend
Creates standalone Windows executable using PyInstaller
"""
import subprocess
import sys
import os
from pathlib import Path

def install_requirements():
    """Install all required packages"""
    print("📦 Installing requirements...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

def build_executable():
    """Build the backend executable using PyInstaller"""
    print("\n🔨 Building backend executable...")
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "api",
        "--onefile",
        "--noconsole",  # No console window
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", ".",
        # Hidden imports for all ML libraries
        "--hidden-import", "numpy",
        "--hidden-import", "pandas",
        "--hidden-import", "scipy",
        "--hidden-import", "scipy.special",
        "--hidden-import", "scipy.stats",
        "--hidden-import", "sklearn",
        "--hidden-import", "sklearn.utils",
        "--hidden-import", "sklearn.cluster",
        "--hidden-import", "sklearn.preprocessing",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "fastapi",
        "--hidden-import", "pydantic",
        "--hidden-import", "starlette",
        "--hidden-import", "nba_api",
        "--hidden-import", "nba_api.stats",
        "--hidden-import", "nba_api.stats.endpoints",
        "--hidden-import", "pybreaker",
        "--hidden-import", "psutil",
        "--hidden-import", "bs4",
        "--hidden-import", "requests",
        "--hidden-import", "aiohttp",
        "--hidden-import", "google.generativeai",
        # Add data files
        "--add-data", "data;data",
        "--add-data", "aegis;aegis",
        "--add-data", "engines;engines",
        "--add-data", "services;services",
        "--add-data", "core;core",
        # Entry point
        "server.py"
    ]
    
    subprocess.run(cmd, check=True)
    
    print("\n✅ Build complete!")
    print(f"   Executable: {Path('dist/api.exe').absolute()}")

def main():
    os.chdir(Path(__file__).parent)
    
    print("=" * 60)
    print("QuantSight Backend Build")
    print("=" * 60)
    
    # Install requirements first
    install_requirements()
    
    # Build executable
    build_executable()
    
    print("\n" + "=" * 60)
    print("Build successful! Run 'npm run electron:build:win' to create installer.")
    print("=" * 60)

if __name__ == "__main__":
    main()
