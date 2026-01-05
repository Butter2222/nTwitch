"""Build script to create standalone executable for Twitch Terminal Viewer."""
import subprocess
import sys
import os
from pathlib import Path

def build_exe():
    """Build the executable using PyInstaller."""
    
    print("="*60)
    print("Building Twitch Terminal Viewer Executable")
    print("="*60)
    print()
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print("[OK] PyInstaller found")
    except ImportError:
        print("[ERROR] PyInstaller not found!")
        print("\nInstalling PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("[OK] PyInstaller installed")
    
    print("\nBuilding executable...")
    print("-"*60)
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=TwitchViewer",
        "--onefile",  # Single executable
        "--console",  # Console application
        "--icon=NONE",  # No icon (can be added later)
        "--add-data=requirements.txt:.",  # Include requirements for reference
        "--hidden-import=blessed.sequences",
        "--hidden-import=blessed.formatters",
        "--hidden-import=blessed.keyboard",
        "--hidden-import=blessed.terminal",
        "--hidden-import=asyncio",
        "--hidden-import=aiofiles",
        "--collect-all=blessed",
        "--clean",  # Clean build
        "twitch_viewer.py"
    ]
    
    # Run PyInstaller
    try:
        result = subprocess.run(cmd, check=True)
        
        print("\n" + "="*60)
        print("BUILD SUCCESSFUL!")
        print("="*60)
        print("\nExecutable location:")
        print(f"  dist/TwitchViewer.exe")
        print("\nYou can now:")
        print("  1. Copy dist/TwitchViewer.exe to any location")
        print("  2. Run it to start the Twitch Terminal Viewer")
        print("  3. Config will be saved in: %USERPROFILE%\\.twitch-terminal-config.json")
        print("\nNote: Streamlink must be installed separately on the target system:")
        print("  pip install streamlink")
        
    except subprocess.CalledProcessError as e:
        print("\n" + "="*60)
        print("BUILD FAILED!")
        print("="*60)
        print(f"\nError: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)
