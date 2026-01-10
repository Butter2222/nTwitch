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
    
    # Constants
    STREAM_LAUNCH_DELAY = 2  # Delay between launching multiple streams
    PROCESS_START_CHECK_DELAY = 0.5  # Wait before checking if process started
    PROCESS_TERMINATE_TIMEOUT = 3  # Seconds to wait for graceful termination
    STREAM_TIMEOUT = 60  # Streamlink stream timeout
    RETRY_STREAMS = 5  # Retry fetching stream info
    RETRY_MAX = 10  # Retry connection attempts
    RETRY_OPEN = 3  # Retry opening stream
    
    def __init__(self, vlc_path: str, quality: str = "best", auto_restart: bool = True):
        """Initialize stream manager."""
        self.vlc_path = vlc_path
        self.quality = quality
        self.streams: List[StreamProcess] = []
        self.auto_restart = auto_restart  # Auto-restart dead streams
        self._restart_count: Dict[str, int] = {}  # Track restart attempts per channel
        self._max_restarts_per_channel = 3  # Max auto-restarts before giving up
    
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
            # VLC arguments - only well-supported options for compatibility
            # BUFFER SETTINGS: Change these values to add more buffering if needed
            # --network-caching=1000 means 1 second buffer (increase for more stability, decrease for lower latency)
            vlc_args = [
                "--no-video-title-show",
                f"--video-title={channel}",
                "--network-caching=1500",      # 1.5 second buffer
                "--no-audio-time-stretch",     # Prevent audio stretching
                "--no-drop-late-frames",       # Don't drop late frames
                "--no-skip-frames",            # Don't skip frames
                "--no-sub-autodetect-file"     # Don't look for subtitles
            ]
            
            # Build streamlink command with compatible stability options
            cmd = [
                "streamlink",
                f"--player={self.vlc_path}",
                f"--player-args={' '.join(vlc_args)}",
                "--stream-timeout=120",              # Increased from 60 to 120 seconds
                "--retry-streams=10",                # Increased from 5 to 10
                "--retry-max=20",                    # Increased from 10 to 20
                "--retry-open=5",                    # Increased from 3 to 5
                "--ringbuffer-size=32M",             # 32MB ring buffer for stability
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
                
                # Auto-restart if enabled
                if self.auto_restart:
                    restart_count = self._restart_count.get(stream.channel, 0)
                    if restart_count < self._max_restarts_per_channel:
                        logger.info(f"Attempting to restart stream for {stream.channel} (attempt {restart_count + 1}/{self._max_restarts_per_channel})")
                        self._restart_stream(stream.channel)
                    else:
                        logger.error(f"Max restart attempts reached for {stream.channel}, giving up")
        
        # Remove dead streams from list (but not restarted ones)
        self.streams = [s for s in self.streams if s.process.poll() is None]
        
        return dead_channels
    
    def _restart_stream(self, channel: str):
        """Restart a dead stream."""
        try:
            # Track restart attempt
            self._restart_count[channel] = self._restart_count.get(channel, 0) + 1
            
            # Launch new stream process
            process = self._launch_single_stream(channel)
            if process:
                self.streams.append(StreamProcess(
                    channel=channel,
                    process=process,
                    pid=process.pid
                ))
                logger.info(f"Successfully restarted stream for {channel}")
                return True
            else:
                logger.error(f"Failed to restart stream for {channel}")
                return False
        except Exception as e:
            logger.error(f"Error restarting stream for {channel}: {e}")
            return False
    
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
        # Remove trailing slashes
        
