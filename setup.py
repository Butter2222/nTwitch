"""Initial setup flow for Twitch Terminal Viewer."""
import subprocess
import sys
import platform
import os
from pathlib import Path
from typing import Optional, List
from config_manager import ConfigManager


def clear_terminal():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


class SetupWizard:
    """Handles initial setup and configuration."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize setup wizard."""
        self.config_manager = config_manager
        self.config = config_manager.get_default_config()
    
    def run(self) -> bool:
        """Run the complete setup wizard."""
        clear_terminal()
        print("=" * 60)
        print("Twitch Terminal Viewer - Initial Setup")
        print("=" * 60)
        print()
        
        # Step 1: VLC Path
        if not self._setup_vlc():
            return False
        
        clear_terminal()
        
        # Step 2: Streamlink Check
        if not self._check_streamlink():
            return False
        
        clear_terminal()
        
        # Step 3: Recording Path
        self._setup_recording_path()
        
        clear_terminal()
        
        # Step 4: Twitch Authentication (Optional)
        self._setup_twitch_auth()
        
        clear_terminal()
        
        # Save configuration
        if self.config_manager.save(self.config):
            print("=" * 60)
            print("Setup Complete!")
            print("=" * 60)
            print("\n✓ Configuration saved successfully!")
            print(f"Config file: {self.config_manager.config_path}")
            return True
        else:
            print("\n✗ Failed to save configuration.")
            return False
    
    def _setup_vlc(self) -> bool:
        """Setup VLC executable path."""
        print("Step 1: VLC Media Player")
        print("-" * 60)
        
        # Try to auto-detect VLC
        vlc_path = self._detect_vlc()
        
        if vlc_path:
            print(f"✓ VLC found: {vlc_path}")
            use_detected = input("Use this path? (Y/n): ").strip().lower()
            if use_detected != 'n':
                self.config["vlc_path"] = str(vlc_path)
                return self._validate_vlc(str(vlc_path))
        
        # Manual input
        print("\nVLC not auto-detected. Please provide the path manually.")
        while True:
            vlc_input = input("VLC executable path (or 'quit' to exit): ").strip()
            if vlc_input.lower() == 'quit':
                return False
            
            if self._validate_vlc(vlc_input):
                self.config["vlc_path"] = vlc_input
                return True
            else:
                print("✗ Invalid VLC path. Please try again.")
    
    def _detect_vlc(self) -> Optional[Path]:
        """Auto-detect VLC installation."""
        system = platform.system()
        possible_paths: List[Path] = []
        
        if system == "Windows":
            possible_paths = [
                Path("C:/Program Files/VideoLAN/VLC/vlc.exe"),
                Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe"),
            ]
        elif system == "Darwin":  # macOS
            possible_paths = [
                Path("/Applications/VLC.app/Contents/MacOS/VLC"),
            ]
        elif system == "Linux":
            possible_paths = [
                Path("/usr/bin/vlc"),
                Path("/usr/local/bin/vlc"),
                Path("/snap/bin/vlc"),
            ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def _validate_vlc(self, vlc_path: str) -> bool:
        """Validate VLC executable by checking if file exists and is executable."""
        try:
            path = Path(vlc_path)
            # Check if file exists
            if not path.exists():
                return False
            
            # Check if it's a file (not directory)
            if not path.is_file():
                return False
            
            # On Unix systems, check if executable
            if sys.platform != 'win32':
                import os
                if not os.access(vlc_path, os.X_OK):
                    return False
            
            # On Windows, just check it's a .exe file
            if sys.platform == 'win32' and not vlc_path.lower().endswith('.exe'):
                return False
            
            return True
        except (FileNotFoundError, OSError):
            return False
    
    def _check_streamlink(self) -> bool:
        """Check if streamlink is installed."""
        print("\nStep 2: Streamlink")
        print("-" * 60)
        
        try:
            result = subprocess.run(
                ["streamlink", "--version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                print(f"✓ Streamlink found: {version}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        # Streamlink not found
        print("✗ Streamlink not found!")
        print("\nStreamlink is required for video streaming.")
        print("\nInstallation instructions:")
        print("  pip install streamlink")
        print("\nOr visit: https://streamlink.github.io/install.html")
        print("\nPlease install Streamlink and run setup again.")
        return False
    
    def _setup_recording_path(self) -> None:
        """Setup recording directory path."""
        print("\nStep 3: Recording Path")
        print("-" * 60)
        
        default_path = self.config.get("recording_path", str(Path.home() / "Videos" / "TwitchRecordings"))
        print(f"Default recording path: {default_path}")
        print()
        
        use_default = input("Use default path? (Y/n): ").strip().lower()
        if use_default != 'n':
            self.config["recording_path"] = default_path
            print(f"✓ Recordings will be saved to: {default_path}")
            return
        
        # Custom path input
        while True:
            custom_path = input("Enter custom recording path: ").strip()
            if not custom_path:
                print("Using default path.")
                self.config["recording_path"] = default_path
                break
            
            try:
                path = Path(custom_path)
                # Try to create the directory
                path.mkdir(parents=True, exist_ok=True)
                self.config["recording_path"] = str(path)
                print(f"✓ Recordings will be saved to: {path}")
                break
            except Exception as e:
                print(f"✗ Invalid path or cannot create directory: {e}")
                print("Please try again or press Enter for default.")
    
    def _setup_twitch_auth(self) -> None:
        """Setup Twitch OAuth token (optional)."""
        print("\nStep 4: Twitch Authentication (Optional)")
        print("-" * 60)
        print("To read and send chat messages, you need a Twitch OAuth token.")
        print("Without it, you can watch video in read-only chat mode.")
        print()
        
        setup_auth = input("Configure Twitch authentication? (Y/n): ").strip().lower()
        if setup_auth == 'n':
            print("Skipping authentication. You can configure it later with --setup.")
            return
        
        print("\nTo get your OAuth token:")
        print("1. Visit: https://twitchtokengenerator.com/")
        print("2. Select 'Bot Chat Token' or 'Custom Scopes'")
        print("3. Authorize the application")
        print("4. Copy the 'Access Token'")
        print()
        
        # Get OAuth token
        while True:
            oauth = input("Paste your Access Token (or press Enter to skip): ").strip()
            if not oauth:
                print("Skipping authentication.")
                return
            
            # Add oauth: prefix if not present
            if not oauth.startswith("oauth:"):
                oauth = f"oauth:{oauth}"
            
            self.config["twitch_oauth"] = oauth
            print("✓ Token configured")
            break
        
        # Get username
        username = input("Enter your Twitch username: ").strip().lower()
        if username:
            self.config["twitch_username"] = username
            print(f"✓ Authentication configured for user: {username}")
        else:
            print("✗ Username required for authentication.")
            self.config["twitch_oauth"] = ""
            return
        
        print("\n⚠ Security Warning:")
        print("The OAuth token will be stored in plaintext in your config file.")
        print(f"Location: {self.config_manager.config_path}")


def run_setup() -> bool:
    """Run the setup wizard."""
    config_manager = ConfigManager()
    wizard = SetupWizard(config_manager)
    return wizard.run()


if __name__ == "__main__":
    success = run_setup()
    sys.exit(0 if success else 1)
