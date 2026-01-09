#!/usr/bin/env python3
"""
Build Python server as standalone executable for Tauri sidecar

Uses PyInstaller to create a standalone executable that can be bundled
with the Tauri application.
"""

import subprocess
import sys
from pathlib import Path


def build_with_pyinstaller():
    """Build using PyInstaller"""
    script_dir = Path(__file__).parent.parent
    server_script = script_dir / "server_p2p.py"
    output_dir = script_dir / "src-tauri" / "sidecar"
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name", "project-dawn-server",
        "--onefile",
        "--console",
        "--distpath", str(output_dir),
        "--workpath", str(script_dir / "build"),
        "--specpath", str(script_dir / "build"),
        "--add-data", f"{script_dir / 'frontend'}:frontend",
        "--add-data", f"{script_dir / 'agents'}:agents",
        "--add-data", f"{script_dir / 'mcp'}:mcp",
        "--add-data", f"{script_dir / 'p2p'}:p2p",
        "--add-data", f"{script_dir / 'crypto'}:crypto",
        "--add-data", f"{script_dir / 'consensus'}:consensus",
        "--add-data", f"{script_dir / 'host'}:host",
        "--hidden-import", "asyncio",
        "--hidden-import", "websockets",
        "--hidden-import", "aiohttp",
        str(server_script),
    ]
    
    print("Building Python server with PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✓ Build successful!")
        print(f"Executable: {output_dir / 'project-dawn-server'}")
        if sys.platform == "win32":
            print(f"Executable: {output_dir / 'project-dawn-server.exe'}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ PyInstaller not found!")
        print("Install it with: pip install pyinstaller")
        return False


def build_with_nuitka():
    """Build using Nuitka (alternative)"""
    script_dir = Path(__file__).parent.parent
    server_script = script_dir / "server_p2p.py"
    output_dir = script_dir / "src-tauri" / "sidecar"
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Nuitka command
    cmd = [
        "python", "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--output-dir", str(output_dir),
        "--output-filename", "project-dawn-server",
        str(server_script),
    ]
    
    print("Building Python server with Nuitka...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✓ Build successful!")
        print(f"Executable: {output_dir / 'project-dawn-server'}")
        if sys.platform == "win32":
            print(f"Executable: {output_dir / 'project-dawn-server.exe'}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        return False
    except FileNotFoundError:
        print("\n✗ Nuitka not found!")
        print("Install it with: pip install nuitka")
        return False


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--nuitka":
        success = build_with_nuitka()
    else:
        success = build_with_pyinstaller()
    
    if not success:
        print("\nTrying alternative build method...")
        if len(sys.argv) > 1 and sys.argv[1] == "--nuitka":
            success = build_with_pyinstaller()
        else:
            success = build_with_nuitka()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
