"""Stream management for launching VLC windows with Streamlink."""
import subprocess
import time
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class StreamProcess:
    """Represents a running stream process."""
    channel: str
    process: subprocess.Popen
    pid: int


class StreamManager:
    """Manages multiple VLC stream processes."""
    
    def __init__(self, vlc_path: str, quality: str = "best"):
        """Initialize stream manager."""
        self.vlc_path = vlc_path
        self.quality = quality
        self.streams: List[StreamProcess] = []
    
    def launch_streams(self, channels: List[str]) -> Dict[str, bool]:
        """
        Launch VLC streams for multiple channels.
        
        Returns dict mapping channel names to success status.
        """
        results = {}
        
        for i, channel in enumerate(channels):
            logger.info(f"Launching stream for channel: {channel}")
            
            try:
                process = self._launch_single_stream(channel)
                if process:
                    self.streams.append(StreamProcess(
                        channel=channel,
                        process=process,
                        pid=process.pid
                    ))
                    results[channel] = True
                    logger.info(f"[OK] Stream launched for {channel} (PID: {process.pid})")
                else:
                    results[channel] = False
                    logger.error(f"[FAIL] Failed to launch stream for {channel}")
                
                # Delay between launches to prevent race conditions
                if i < len(channels) - 1:
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error launching stream for {channel}: {e}")
                results[channel] = False
        
        return results
    
    def _launch_single_stream(self, channel: str) -> Optional[subprocess.Popen]:
        """Launch a single VLC stream via Streamlink."""
        try:
            # Build streamlink command (removed --twitch-proxy-playlist for compatibility)
            cmd = [
                "streamlink",
                f"--player={self.vlc_path}",
                f"--player-args=--no-video-title-show --video-title={channel}",
                f"twitch.tv/{channel}",
                self.quality
            ]
            
            # Launch process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            # Give it a moment to fail if it's going to
            time.sleep(0.5)
            
            # Check if process is still running
            if process.poll() is not None:
                if process.stderr:
                    stderr = process.stderr.read().decode('utf-8', errors='ignore')
                    logger.error(f"Stream process died immediately: {stderr}")
                return None
            
            return process
            
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Error launching stream: {e}")
            return None
    
    def check_streams(self) -> List[str]:
        """Check which streams are still running. Returns list of dead channels."""
        dead_channels = []
        
        for stream in self.streams:
            if stream.process.poll() is not None:
                dead_channels.append(stream.channel)
                logger.warning(f"Stream for {stream.channel} has died")
        
        # Remove dead streams from list
        self.streams = [s for s in self.streams if s.channel not in dead_channels]
        
        return dead_channels
    
    def cleanup(self):
        """Terminate all VLC processes."""
        logger.info("Cleaning up stream processes...")
        
        for stream in self.streams:
            try:
                if stream.process.poll() is None:
                    stream.process.terminate()
                    # Give it time to close gracefully
                    try:
                        stream.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        stream.process.kill()
                    logger.info(f"Terminated stream for {stream.channel}")
            except Exception as e:
                logger.error(f"Error terminating stream for {stream.channel}: {e}")
        
        self.streams.clear()
    
    def get_running_channels(self) -> List[str]:
        """Get list of currently running channel names."""
        return [s.channel for s in self.streams]


def parse_channel_input(input_str: str) -> List[str]:
    """
    Parse channel input string into list of normalized channel names.
    
    Handles formats:
    - Single: "xqc"
    - Multiple: "xqc, hasanabi, pokimane"
    - URLs: "twitch.tv/xqc", "https://www.twitch.tv/xqc"
    """
    channels = []
    
    # Split by comma
    parts = [p.strip() for p in input_str.split(',')]
    
    for part in parts:
        if not part:
            continue
        
        # Extract channel name from URL if present
        channel = part.lower()
        
        # Remove protocol
        if channel.startswith('https://'):
            channel = channel[8:]
        elif channel.startswith('http://'):
            channel = channel[7:]
        
        # Remove domain
        if channel.startswith('www.twitch.tv/'):
            channel = channel[14:]
        elif channel.startswith('twitch.tv/'):
            channel = channel[10:]
        
        # Remove trailing slashes
        channel = channel.rstrip('/')
        
        # Add if not empty and not duplicate
        if channel and channel not in channels:
            channels.append(channel)
    
    return channels
