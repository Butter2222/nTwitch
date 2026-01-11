"""Configuration management for Twitch Terminal Viewer."""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigManager:
    """Handles configuration file operations."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager with path to config file."""
        if config_path is None:
            home = Path.home()
            self.config_path = home / ".twitch-terminal-config.json"
        else:
            self.config_path = Path(config_path)
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config: {e}")
            return {}
    
    def save(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error: Could not save config: {e}")
            return False
    
    def exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_path.exists()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure."""
        from pathlib import Path
        default_recordings = str(Path.home() / "Videos" / "TwitchRecordings")
        return {
            "vlc_path": "",
            "twitch_username": "",
            "twitch_oauth": "",
            "streamlink_quality": "best",
            "chat_colors_enabled": True,
            "recording_path": default_recordings
        }
