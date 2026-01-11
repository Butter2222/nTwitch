"""Sophisticated clip manager with rolling buffer for instant replay clips."""
import subprocess
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass
import asyncio
import time


logger = logging.getLogger(__name__)


@dataclass
class ClipBuffer:
    """Represents an active clip buffer."""
    channel: str
    process: subprocess.Popen
    temp_file: Path
    start_time: float
    buffer_minutes: int


class ClipManager:
    """Manages rolling buffer recording for instant clip saving."""
    
    def __init__(self, quality: str = "best", buffer_minutes: int = 10, clips_path: Optional[str] = None):
        """Initialize clip manager.
        
        Args:
            quality: Stream quality to record
            buffer_minutes: How many minutes to keep in buffer (minimum 10)
            clips_path: Path to save clips (default: ~/Videos/TwitchClips)
        """
        self.quality = quality
        self.buffer_minutes = max(10, buffer_minutes)  # Minimum 10 minutes
        self.active_buffer: Optional[ClipBuffer] = None
        self.clips_path = self._get_clips_path(clips_path)
        self.temp_path = self.clips_path / ".temp"
        
        # Create directories
        self.clips_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        
        # Clean old temp files on startup
        self._cleanup_temp_files()
        
        logger.info(f"Clip manager initialized: {self.buffer_minutes}min buffer, saving to {self.clips_path}")
    
    def _get_clips_path(self, custom_path: Optional[str] = None) -> Path:
        """Get the clips directory path."""
        if custom_path:
            return Path(custom_path)
        # Default: Videos/TwitchClips
        videos_folder = Path.home() / "Videos"
        clips_folder = videos_folder / "TwitchClips"
        return clips_folder
    
    def _cleanup_temp_files(self):
        """Clean up old temporary buffer files."""
        try:
            for temp_file in self.temp_path.glob("*.ts"):
                try:
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_file}: {e}")
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
    
    def is_buffering(self, channel: str) -> bool:
        """Check if a channel is currently being buffered."""
        return self.active_buffer is not None and self.active_buffer.channel == channel
    
    def get_active_buffer_channel(self) -> Optional[str]:
        """Get the channel currently being buffered."""
        if self.active_buffer:
            return self.active_buffer.channel
        return None
    
    def start_buffer(self, channel: str) -> bool:
        """Start rolling buffer for a channel.
        
        Only one channel can be buffered at a time.
        If switching channels, the old buffer is discarded.
        """
        # Stop existing buffer if switching channels
        if self.active_buffer and self.active_buffer.channel != channel:
            logger.info(f"Switching buffer from {self.active_buffer.channel} to {channel}")
            self._stop_buffer_process()
        
        # Already buffering this channel
        if self.is_buffering(channel):
            logger.debug(f"Already buffering {channel}")
            return True
        
        try:
            # Create temporary file for rolling buffer
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = self.temp_path / f"{channel}_{timestamp}_buffer.ts"
            
            # Build streamlink command with rolling buffer using HLS segments
            # We'll use a temporary file that gets continuously written to
            cmd = [
                "streamlink",
                "--force",
                "--hls-live-edge", "6",  # Stay 6 segments from live edge
                f"twitch.tv/{channel}",
                self.quality,
                "-o", str(temp_file)
            ]
            
            # Start buffering process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            # Store buffer info
            self.active_buffer = ClipBuffer(
                channel=channel,
                process=process,
                temp_file=temp_file,
                start_time=time.time(),
                buffer_minutes=self.buffer_minutes
            )
            
            logger.info(f"Started {self.buffer_minutes}min buffer for {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting buffer for {channel}: {e}")
            return False
    
    def _stop_buffer_process(self):
        """Stop the active buffer process."""
        if not self.active_buffer:
            return
        
        try:
            # Terminate the process
            self.active_buffer.process.terminate()
            try:
                self.active_buffer.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.active_buffer.process.kill()
            
            # Delete temp file
            if self.active_buffer.temp_file.exists():
                try:
                    self.active_buffer.temp_file.unlink()
                    logger.debug(f"Deleted temp buffer: {self.active_buffer.temp_file}")
                except Exception as e:
                    logger.warning(f"Could not delete temp buffer: {e}")
            
        except Exception as e:
            logger.error(f"Error stopping buffer process: {e}")
        finally:
            self.active_buffer = None
    
    def stop_buffer(self, channel: str) -> bool:
        """Stop buffering for a channel (discards buffer)."""
        if not self.is_buffering(channel):
            logger.warning(f"Not buffering {channel}")
            return False
        
        logger.info(f"Stopping buffer for {channel}")
        self._stop_buffer_process()
        return True
    
    def save_clip(self, channel: str) -> tuple[bool, str, Optional[Path]]:
        """Save the current buffer as a clip.
        
        Returns: (success, message, clip_path)
        """
        if not self.is_buffering(channel) or not self.active_buffer:
            return False, f"Not buffering {channel}. Start buffer first.", None
        
        # Check buffer age
        buffer_age_seconds = time.time() - self.active_buffer.start_time
        buffer_age_minutes = buffer_age_seconds / 60
        
        if buffer_age_minutes < 1:
            return False, f"Buffer too short ({buffer_age_minutes:.1f}min). Wait at least 1 minute.", None
        
        try:
            # Create output directory
            channel_folder = self.clips_path / channel
            channel_folder.mkdir(parents=True, exist_ok=True)
            
            # Generate clip filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clip_duration = min(int(buffer_age_minutes), self.buffer_minutes)
            clip_file = channel_folder / f"{channel}_clip_{timestamp}_{clip_duration}min.mp4"
            
            # Check if temp file exists and has content
            if not self.active_buffer.temp_file.exists():
                return False, "Buffer file not found. Try again.", None
            
            file_size = self.active_buffer.temp_file.stat().st_size
            if file_size < 1000000:  # Less than 1MB
                return False, f"Buffer too small ({file_size} bytes). Wait longer.", None
            
            logger.info(f"Saving clip from {channel}: {clip_duration}min buffer -> {clip_file}")
            
            # Copy the buffer file to permanent clip location
            # We need to re-encode to MP4 and extract the last N minutes
            # Using ffmpeg to get the last N minutes
            import shutil
            
            # Calculate how much to extract (last N minutes or entire buffer)
            extract_duration = min(buffer_age_seconds, self.buffer_minutes * 60)
            
            # Use ffmpeg to extract the last N minutes and convert to MP4
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", str(self.active_buffer.temp_file),
                "-c", "copy",  # Copy codecs (fast)
                "-t", str(int(extract_duration)),  # Duration to extract
                "-y",  # Overwrite output file
                str(clip_file)
            ]
            
            # Try ffmpeg first, fallback to simple copy
            try:
                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    logger.info(f"Clip saved successfully: {clip_file}")
                else:
                    # Fallback: just copy the file
                    logger.warning("ffmpeg failed, using direct copy")
                    shutil.copy2(self.active_buffer.temp_file, clip_file)
            
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # ffmpeg not available or timeout, just copy
                logger.warning("ffmpeg not available, using direct copy")
                shutil.copy2(self.active_buffer.temp_file, clip_file)
            
            # Verify clip was created
            if not clip_file.exists():
                return False, "Failed to save clip file.", None
            
            clip_size_mb = clip_file.stat().st_size / (1024 * 1024)
            
            return True, f"Clip saved: {clip_file.name} ({clip_size_mb:.1f}MB)", clip_file
            
        except Exception as e:
            logger.error(f"Error saving clip: {e}")
            return False, f"Error saving clip: {e}", None
    
    def get_buffer_status(self, channel: str) -> Optional[str]:
        """Get buffer status for a channel (time buffered)."""
        if not self.is_buffering(channel):
            return None
        
        buffer_age_seconds = time.time() - self.active_buffer.start_time
        buffer_minutes = int(buffer_age_seconds / 60)
        buffer_seconds = int(buffer_age_seconds % 60)
        
        max_min = self.buffer_minutes
        
        if buffer_minutes >= max_min:
            return f"READY {max_min}:00"
        else:
            return f"{buffer_minutes:02d}:{buffer_seconds:02d}/{max_min}"
    
    def cleanup(self):
        """Clean up all buffers and temp files."""
        logger.info("Cleaning up clip manager...")
        
        if self.active_buffer:
            self._stop_buffer_process()
        
        self._cleanup_temp_files()
        
        logger.info("Clip manager cleanup complete")
