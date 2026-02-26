"""
Proto Generation Script — Phase 6 Step 6.2
============================================
Generates Python gRPC stubs from vanguard.proto.
Fails if vanguard.proto is newer than generated files.

Usage:
    python scripts/generate_proto.py
"""
import os
import sys
import subprocess
from pathlib import Path


def main():
    backend_dir = Path(__file__).parent.parent
    proto_dir = backend_dir / "vanguard" / "proto"
    generated_dir = proto_dir / "generated"
    proto_file = proto_dir / "vanguard.proto"

    if not proto_file.exists():
        print(f"ERROR: {proto_file} not found")
        sys.exit(1)

    generated_dir.mkdir(parents=True, exist_ok=True)

    # Check if regeneration is needed
    pb2_file = generated_dir / "vanguard_pb2.py"
    grpc_file = generated_dir / "vanguard_pb2_grpc.py"

    if pb2_file.exists() and grpc_file.exists():
        proto_mtime = proto_file.stat().st_mtime
        pb2_mtime = pb2_file.stat().st_mtime
        grpc_mtime = grpc_file.stat().st_mtime
        if proto_mtime <= min(pb2_mtime, grpc_mtime):
            print("Generated files are up-to-date. Skipping.")
            return

    print(f"Generating proto stubs from {proto_file}...")

    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={generated_dir}",
        f"--grpc_python_out={generated_dir}",
        str(proto_file),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: protoc failed:\n{result.stderr}")
        sys.exit(1)

    # Fix the import in the generated gRPC file.
    # grpc_tools generates: import vanguard_pb2 as vanguard__pb2
    # But we need: from . import vanguard_pb2 as vanguard__pb2
    # (because the generated files live inside a package)
    grpc_content = grpc_file.read_text(encoding="utf-8")
    fixed = grpc_content.replace(
        "import vanguard_pb2 as vanguard__pb2",
        "from . import vanguard_pb2 as vanguard__pb2",
    )
    if fixed != grpc_content:
        grpc_file.write_text(fixed, encoding="utf-8")
        print("Fixed relative import in vanguard_pb2_grpc.py")

    # Verify
    print("Verifying generated stubs...")
    verify_cmd = [
        sys.executable, "-c",
        "from vanguard.proto.generated import vanguard_pb2; "
        "print('  vanguard_pb2 OK:', dir(vanguard_pb2)[:5]); "
        "from vanguard.proto.generated import vanguard_pb2_grpc; "
        "print('  vanguard_pb2_grpc OK:', dir(vanguard_pb2_grpc)[:5])"
    ]
    verify = subprocess.run(verify_cmd, capture_output=True, text=True, cwd=str(backend_dir))
    if verify.returncode != 0:
        print(f"ERROR: Verification failed:\n{verify.stderr}")
        sys.exit(1)
    print(verify.stdout)
    print("Proto generation complete.")


if __name__ == "__main__":
    main()
