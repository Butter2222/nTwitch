"""Main application entry point for Twitch Terminal Viewer."""
import asyncio
import sys
import argparse
import logging
import signal
from typing import Optional, Union

from config_manager import ConfigManager
from setup import run_setup
from stream_manager import StreamManager, parse_channel_input
from chat_client import ChatManager, ChatMessage
from terminal_ui import MultiChannelUI, SimpleUI
from input_handler import InputHandler
from recording_manager import RecordingManager
from clip_manager import ClipManager


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitch_viewer.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


class TwitchViewer:
    """Main application class."""
    
    def __init__(self, config: dict, channels: list, no_chat: bool = False,
                 quality: str = "best", use_simple_ui: bool = False):
        """Initialize the viewer."""
        self.config = config
        self.channels = channels
        self.no_chat = no_chat
        self.quality = quality
        self.use_simple_ui = use_simple_ui
        
        # Components
        self.stream_manager: Optional[StreamManager] = None
        self.chat_manager: Optional[ChatManager] = None
        self.ui: Optional[Union[MultiChannelUI, SimpleUI]] = None
        self.recording_manager: Optional[RecordingManager] = None
        self.clip_manager: Optional[ClipManager] = None
        
        # State
        self.running = False
        self.input_task: Optional[asyncio.Task] = None
        self.render_task: Optional[asyncio.Task] = None
        self.input_handler: Optional[InputHandler] = None
    
    async def start(self):
        """Start the viewer."""
        logger.info("Starting Twitch Viewer...")
        self.running = True
        
        # Step 1: Launch video streams
        logger.info(f"Launching streams for {len(self.channels)} channel(s)...")
        self.stream_manager = StreamManager(
            vlc_path=self.config['vlc_path'],
            quality=self.quality
        )
        
        results = self.stream_manager.launch_streams(self.channels)
        
        # Check if any streams launched successfully
        successful_channels = [ch for ch, success in results.items() if success]
        failed_channels = [ch for ch, success in results.items() if not success]
        
        if failed_channels:
            logger.warning(f"Failed to launch streams for: {', '.join(failed_channels)}")
        
        if not successful_channels:
            logger.error("All streams failed to launch. Exiting.")
            return
        
        logger.info(f"Successfully launched {len(successful_channels)} stream(s)")
        print(f"[OK] VLC windows launching (may take 5-15 seconds to start streaming)...")
        
        # Initialize recording manager
        recording_path = self.config.get('recording_path')
        self.recording_manager = RecordingManager(quality=self.quality, recording_path=recording_path)
        print(f"[OK] Recording system ready (Press 'R' to start/stop per channel)")
        print(f"[OK] Recordings saved to: {self.recording_manager.base_path}")
        
        # Initialize clip manager with 10-minute buffer
        clips_path = self.config.get('clips_path')
        self.clip_manager = ClipManager(quality=self.quality, buffer_minutes=10, clips_path=clips_path)
        print(f"[OK] Clip system ready (Press 'C' to save 10min clip of selected channel)")
        print(f"[OK] Clips saved to: {self.clip_manager.clips_path}")
        
        # Step 2: Setup chat (if not disabled)
        if not self.no_chat:
            print("[INFO] Starting chat interface...")
            await self._setup_chat(successful_channels)
        else:
            logger.info("Chat disabled. Video-only mode.")
            print("Video streams launched. Press Ctrl+C to exit.")
            
            # Just wait for user to exit
            try:
                while self.running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
    
    async def _setup_chat(self, channels: list):
        """Setup chat connection and UI."""
        # Determine authentication mode
        token = self.config.get('twitch_oauth', '')
        username = self.config.get('twitch_username', '')
        is_authenticated = bool(token and username)
        
        # Initialize UI with recording manager and clip manager
        if self.use_simple_ui:
            self.ui = SimpleUI(channels, is_authenticated)
        else:
            self.ui = MultiChannelUI(channels, is_authenticated, self.recording_manager, self.clip_manager, username)
        
        self.ui.start()
        
        # Initialize chat manager
        logger.info("Connecting to Twitch chat...")
        self.chat_manager = ChatManager(
            channels=channels,
            message_callback=self._on_message,
            token=token if is_authenticated else None,
            username=username if is_authenticated else None
        )
        
        try:
            await self.chat_manager.connect()
            logger.info("Connected to chat")
            
            # Start UI tasks
            if not self.use_simple_ui:
                self.input_handler = InputHandler()
                self.input_task = asyncio.create_task(
                    self.input_handler.start_input_loop(
                        self._handle_key,
                        lambda: setattr(self, 'running', False)
                    )
                )
                self.render_task = asyncio.create_task(self._render_loop())
                self.recording_update_task = asyncio.create_task(self._recording_update_loop())
            
            # Keep running
            while self.running:
                await asyncio.sleep(1)
                
                # Check for dead streams
                if self.stream_manager:
                    dead = self.stream_manager.check_streams()
                    if dead:
                        for channel in dead:
                            if self.ui:
                                self.ui.set_status(f"⚠ Stream for #{channel} has died")
                
        except Exception as e:
            logger.error(f"Error in chat setup: {e}")
            self.ui.set_status(f"Error: {e}")
    
    def _on_message(self, message: ChatMessage):
        """Handle incoming chat message."""
        if self.ui:
            self.ui.add_message(message)
            if not self.use_simple_ui and isinstance(self.ui, MultiChannelUI):
                # Schedule a render
                pass  # Render loop handles this
    
    async def _handle_key(self, key: str):
        """Handle a key press."""
        if self.ui:
            await self.ui.handle_input(
                key, 
                self._send_message, 
                self._toggle_recording, 
                self._save_clip,
                self._switch_streamers,
                self._on_channel_change
            )
    
    async def _on_channel_change(self, channel: str):
        """Handle channel selection change - auto-start clip buffer."""
        if self.clip_manager and not self.clip_manager.is_buffering(channel):
            self.clip_manager.start_buffer(channel)
            logger.info(f"Auto-started clip buffer for {channel}")
    
    async def _switch_streamers(self):
        """Switch to different streamers."""
        # Stop current UI
        if self.ui:
            self.ui.stop()
        
        # Stop chat
        if self.chat_manager:
            await self.chat_manager.disconnect()
        
        # Stop streams
        if self.stream_manager:
            self.stream_manager.cleanup()
        
        # Stop recordings
        if self.recording_manager:
            self.recording_manager.cleanup()
        
        # Clear console and prompt for new channels
        print("\n" + "="*60)
        print("SWITCH STREAMERS")
        print("="*60)
        print("Enter new Twitch channel(s) to watch (comma separated)")
        print("\nExamples:")
        print("  Single:   xqc")
        print("  Multiple: xqc, hasanabi, pokimane")
        print()
        
        channel_input = input("Channel(s): ").strip()
        
        if not channel_input:
            print("\nNo channels specified. Exiting.")
            self.running = False
            return
        
        from stream_manager import parse_channel_input
        new_channels = parse_channel_input(channel_input)
        
        if not new_channels:
            print("Error: No valid channels specified. Exiting.")
            self.running = False
            return
        
        # Update channels
        self.channels = new_channels
        
        print(f"\nSwitching to: {', '.join(new_channels)}")
        print("Please wait...\n")
        
        # Restart with new channels
        await self.start()
    
    async def _toggle_recording(self, channel: str) -> tuple[bool, str]:
        """Toggle recording for a channel."""
        if self.recording_manager:
            return self.recording_manager.toggle_recording(channel)
        return False, "Recording not available"
    
    async def _save_clip(self, channel: str) -> tuple[bool, str]:
        """Save a clip from the buffer for a channel."""
        if not self.clip_manager:
            return False, "Clip manager not available"
        
        # Start buffer if not already buffering
        if not self.clip_manager.is_buffering(channel):
            self.clip_manager.start_buffer(channel)
            return False, f"Started buffering {channel}. Wait ~10min then press C again."
        
        # Save the clip
        success, message, clip_path = self.clip_manager.save_clip(channel)
        return success, message
    
    async def _recording_update_loop(self):
        """Periodic update loop for recording timers."""
        try:
            while self.running:
                # Trigger render if any recordings are active
                if self.recording_manager and self.recording_manager.recordings:
                    if self.ui and isinstance(self.ui, MultiChannelUI):
                        self.ui.render()
                await asyncio.sleep(1)  # Update every second
        except Exception as e:
            logger.error(f"Error in recording update loop: {e}")
    
    async def _render_loop(self):
        """Periodic UI rendering."""
        try:
            while self.running:
                if self.ui and isinstance(self.ui, MultiChannelUI):
                    # Render at reasonable rate to prevent flickering
                    self.ui.render()
                await asyncio.sleep(0.5)  # 2 FPS - stable and smooth
        except Exception as e:
            logger.error(f"Error in render loop: {e}", exc_info=True)
    
    async def _send_message(self, channel: str, content: str):
        """Send a message to a channel."""
        if self.chat_manager:
            await self.chat_manager.send_message(channel, content)
            # Echo own message back to UI
            if self.ui and self.config.get('twitch_username'):
                own_message = ChatMessage(
                    channel=channel,
                    author=self.config['twitch_username'],
                    content=content,
                    color="#00FF7F",  # Green for own messages
                    badges=[]
                )
                self.ui.add_message(own_message)
    
    async def stop(self):
        """Stop the viewer and cleanup."""
        logger.info("Stopping viewer...")
        self.running = False
        
        # Cancel tasks
        if self.input_task:
            self.input_task.cancel()
            try:
                await self.input_task
            except asyncio.CancelledError:
                pass
        
        if self.render_task:
            self.render_task.cancel()
            try:
                await self.render_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(self, 'recording_update_task') and self.recording_update_task:
            self.recording_update_task.cancel()
            try:
                await self.recording_update_task
            except asyncio.CancelledError:
                pass
        
        # Stop UI
        if self.ui:
            self.ui.stop()
        
        # Disconnect chat
        if self.chat_manager:
            await self.chat_manager.disconnect()
        
        # Stop all recordings
        if self.recording_manager:
            self.recording_manager.cleanup()
        
        # Cleanup clip buffer
        if self.clip_manager:
            self.clip_manager.cleanup()
        
        # Cleanup streams
        if self.stream_manager:
            self.stream_manager.cleanup()
        
        logger.info("Viewer stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Terminal Twitch Viewer')
    parser.add_argument('--setup', action='store_true', help='Run setup wizard')
    parser.add_argument('--config', action='store_true', help='Run setup wizard (alias)')
    parser.add_argument('--channels', type=str, help='Comma-separated channel list')
    parser.add_argument('--quality', type=str, default='best', 
                       help='Stream quality (best, 1080p60, 720p60, etc.)')
    parser.add_argument('--no-chat', action='store_true', help='Video only, no chat')
    parser.add_argument('--anon', action='store_true', help='Force anonymous mode')
    parser.add_argument('--simple-ui', action='store_true', 
                       help='Use simple scrolling UI instead of split-pane')
    
    args = parser.parse_args()
    
    # Handle setup
    if args.setup or args.config:
        success = run_setup()
        sys.exit(0 if success else 1)
    
    # Load configuration
    config_manager = ConfigManager()
    
    if not config_manager.exists():
        print("\n" + "="*60)
        print("FIRST TIME SETUP")
        print("="*60)
        print("Welcome! Let's configure the Twitch Terminal Viewer.\n")
        success = run_setup()
        if not success:
            sys.exit(1)
        # Reload config
        config = config_manager.load()
        print("\n" + "="*60)
        print("Setup complete! Starting viewer...")
        print("="*60 + "\n")
    else:
        config = config_manager.load()
        # Ask if user wants to reconfigure
        print("\n" + "="*60)
        print("TWITCH TERMINAL VIEWER")
        print("="*60)
        change_config = input("\nChange configuration? (y/N): ").strip().lower()
        if change_config == 'y':
            success = run_setup()
            if not success:
                sys.exit(1)
            config = config_manager.load()
    
    # Validate config
    if not config.get('vlc_path'):
        print("Error: VLC path not configured. Run with --setup")
        sys.exit(1)
    
    # Handle anonymous mode
    if args.anon:
        config['twitch_oauth'] = ''
        config['twitch_username'] = ''
    
    # Get channels (always prompt unless --channels specified)
    channels = []
    if args.channels:
        channels = parse_channel_input(args.channels)
    else:
        # Prompt for channels
        print("\n" + "-"*60)
        print("CHANNEL SELECTION")
        print("-"*60)
        print("Enter Twitch channel(s) to watch (comma separated for multiple)")
        print("Maximum recommended: 5 channels")
        print("\nExamples:")
        print("  Single:   xqc")
        print("  Multiple: xqc, hasanabi, pokimane")
        print()
        channel_input = input("Channel(s): ").strip()
        
        if not channel_input:
            print("\nNo channels specified. Exiting.")
            sys.exit(1)
        
        channels = parse_channel_input(channel_input)
    
    if not channels:
        print("Error: No valid channels specified.")
        sys.exit(1)
    
    # Warn if too many channels
    if len(channels) > 5:
        print(f"\nWarning: {len(channels)} channels requested.")
        print("Performance may degrade with many channels.")
        response = input("Continue? (y/N): ").strip().lower()
        if response != 'y':
            sys.exit(0)
    
    print(f"\nLaunching viewer for: {', '.join(channels)}")
    print("Please wait...\n")
    
    # Create and run viewer
    viewer = TwitchViewer(
        config=config,
        channels=channels,
        no_chat=args.no_chat,
        quality=args.quality,
        use_simple_ui=args.simple_ui
    )
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received interrupt signal")
        viewer.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run async main loop
    try:
        asyncio.run(viewer.start())
    except KeyboardInterrupt:
        pass
    finally:
        # Final cleanup
        if viewer.running:
            asyncio.run(viewer.stop())
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
