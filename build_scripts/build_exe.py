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
    
    # Change to parent directory (project root)
    project_root = Path(__file__).parent.parent
    build_scripts_dir = Path(__file__).parent
    os.chdir(project_root)
    
    # PyInstaller command with output directories in build_scripts
    cmd = [
        "pyinstaller",
        "--name=nTwitch",
        "--onefile",  # Single executable
        "--console",  # Console application
        "--icon=NONE",  # No icon (can be added later)
        "--add-data=requirements.txt:.",  # Include requirements for reference
        "--distpath=build_scripts/dist",  # Output executable to build_scripts/dist
        "--workpath=build_scripts/build",  # Build files to build_scripts/build
        "--specpath=build_scripts",  # Spec file in build_scripts
        "--hidden-import=blessed.sequences",
        "--hidden-import=blessed.formatters",
        "--hidden-import=blessed.keyboard",
        "--hidden-import=blessed.terminal",
        "--hidden-import=asyncio",
        "--hidden-import=aiofiles",
        "--hidden-import=src.config_manager",
        "--hidden-import=src.setup",
        "--hidden-import=src.stream_manager",
        "--hidden-import=src.chat_client",
        "--hidden-import=src.terminal_ui",
        "--hidden-import=src.recording_manager",
        "--hidden-import=src.clip_manager",
        "--hidden-import=src.input_handler",
        "--collect-all=blessed",
        "--paths=src",  # Add src to Python path
        "--clean",  # Clean build
        "nTwitch.py"
    ]
    
    # Run PyInstaller
    try:
        result = subprocess.run(cmd, check=True)
        
        print("\n" + "="*60)
        print("BUILD SUCCESSFUL!")
        print("="*60)
        print("\nExecutable location:")
        print(f"  build_scripts/dist/nTwitch.exe")
        print("\nYou can now:")
        print("  1. Copy build_scripts/dist/nTwitch.exe to any location")
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
