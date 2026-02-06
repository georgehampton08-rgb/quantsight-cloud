"""
Build the SMALL launcher executable.
This creates a tiny exe (~5MB) that downloads Python + deps on first run.
Much faster than bundling all ML libraries.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    os.chdir(Path(__file__).parent)
    
    print("=" * 60)
    print("Building QuantSight Launcher (Small Bootstrap)")
    print("=" * 60)
    
    # Simple PyInstaller command - just the launcher
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "api",
        "--onefile",
        "--noconsole",
        "--distpath", "dist",
        "--workpath", "build",
        "--clean",
        "launcher.py"
    ]
    
    print("\n🔨 Building launcher executable...")
    subprocess.run(cmd, check=True)
    
    # Copy backend files to dist
    dist_dir = Path("dist")
    backend_files = ["server.py", "requirements.txt", "data_paths.py"]
    backend_dirs = ["aegis", "engines", "services", "core", "data"]
    
    print("\n📁 Copying backend files...")
    for f in backend_files:
        if Path(f).exists():
            import shutil
            shutil.copy(f, dist_dir / f)
            print(f"   Copied {f}")
    
    for d in backend_dirs:
        if Path(d).exists():
            import shutil
            dest = dist_dir / d
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(d, dest)
            print(f"   Copied {d}/")
    
    print("\n✅ Build complete!")
    print(f"   Launcher: {(dist_dir / 'api.exe').absolute()}")
    print("\nThis launcher will download Python + dependencies on first run.")
    print("Total installer size: ~10MB (vs ~500MB with bundled Python)")

if __name__ == "__main__":
    main()
