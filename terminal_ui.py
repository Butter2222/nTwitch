import asyncio
import logging
from typing import List, Dict, Optional, Callable
from collections import deque
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Static, Input, Footer, Header, RichLog
from textual.reactive import reactive
from textual.binding import Binding
from textual import work, events
from rich.text import Text
from rich.style import Style

from chat_client import ChatMessage

logger = logging.getLogger(__name__)


class ChatInput(Input):
    """Custom Input that doesn't capture Tab key."""
    
    BINDINGS = [
        # Override Tab binding to do nothing, letting it bubble up
    ]


class ChannelPane(Static):
    """A single channel chat pane widget."""
    
    DEFAULT_CSS = """
    ChannelPane {
        border: solid #babaff;
        height: 100%;
        width: 1fr;
        background: #1e1e1e;
        overflow: hidden;
    }
    
    ChannelPane.active {
        border: solid #f9baff !important;
        background: #1e1e1e;
    }
    
    ChannelPane.recording {
        border: solid #ff0000 !important;
        background: #1e1e1e;
    }
    
    ChannelPane > RichLog {
        height: 1fr;
        width: 100%;
        background: #1e1e1e;
        color: #ffffff;
        padding: 0 1;
        overflow-y: auto;
        overflow-x: hidden;
        scrollbar-size: 0 0;
    }
    
    ChannelPane .channel-header {
        text-align: center;
        background: #2d2d2d;
        color: #ffffff;
        padding: 0 1;
        text-style: bold;
    }
    
    ChannelPane.recording .channel-header {
        background: #ff0000;
        color: #ffffff;
    }
    """
    
    def __init__(self, channel: str, max_messages: int = 200):
        """Initialize channel pane."""
        super().__init__()
        self.channel = channel
        self.max_messages = max_messages
        self.messages: deque = deque(maxlen=max_messages)
        self.is_active = False
        self.is_recording = False
        self.recording_duration = ""
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        header_text = f">>> {self.channel.upper()} <<<"
        if self.is_recording:
            header_text += f" [REC {self.recording_duration}]"
        
        yield Static(header_text, classes="channel-header")
        yield RichLog(max_lines=self.max_messages, wrap=True, markup=True)
    
    def add_message(self, message: ChatMessage, my_username: Optional[str] = None):
        """Add a message to the pane."""
        self.messages.append(message)
        
        # Get the RichLog widget
        log = self.query_one(RichLog)
        
        # Format the message with Rich styling
        formatted = self._format_message(message, my_username)
        log.write(formatted)
    
    def _format_message(self, message: ChatMessage, my_username: Optional[str] = None) -> str:
        """Format a chat message with Rich Text styling - returns plain string for proper wrapping."""
        # Build message parts
        parts = []
        
        # Add badge if present
        badge = message.get_badge_text()
        if badge:
            parts.append(badge)
        
        # Add username and colon
        parts.append(f"{message.author}:")
        
        # Add message content
        parts.append(message.content)
        
        # Join and return as plain string - RichLog will handle wrapping
        return " ".join(parts)
    
    def _get_username_style(self, message: ChatMessage) -> Style:
        """Get Rich style for username based on user type."""
        if message.is_broadcaster():
            return Style(color="red", bold=True)
        elif message.is_moderator():
            return Style(color="green", bold=True)
        elif message.color:
            # Use Twitch user color
            try:
                color = message.color.lstrip('#')
                return Style(color=f"#{color}")
            except:
                pass
        elif message.is_subscriber():
            return Style(color="magenta")
        elif message.is_vip():
            return Style(color="magenta", bold=True)
        
        return Style(color="white")
    
    def clear_messages(self):
        """Clear all messages from the pane."""
        self.messages.clear()
        log = self.query_one(RichLog)
        log.clear()
    
    def set_active(self, active: bool):
        """Set whether this pane is active."""
        self.is_active = active
        if active:
            self.add_class("active")
        else:
            self.remove_class("active")
        self._update_header()
        # Force visual refresh
        self.refresh(layout=True)
    
    def set_recording(self, recording: bool, duration: str = ""):
        """Set recording status."""
        self.is_recording = recording
        self.recording_duration = duration
        if recording:
            self.add_class("recording")
        else:
            self.remove_class("recording")
        self._update_header()
    
    def _update_header(self):
        """Update the header text."""
        header_text = f">>> {self.channel.upper()} <<<"
        if self.is_recording:
            header_text += f" [REC {self.recording_duration}]"
        
        # Only update if the widget is mounted
        try:
            header = self.query_one(".channel-header", Static)
            header.update(header_text)
        except:
            pass  # Widget not mounted yet


class StatusBar(Static):
    """Status bar showing active channel and info."""
    
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: #babaff;
        color: $text;
        padding: 0 1;
    }
    """
    
    status_text = reactive("")
    
    def render(self) -> str:
        """Render the status text."""
        return self.status_text
    
    def set_status(self, text: str):
        """Set the status text."""
        self.status_text = text


class MultiChannelUI(App):
    """Textual-based multi-channel Twitch viewer UI."""
    
    # Remove app title from header
    TITLE = ""
    
    # Reactive property for placeholder text
    input_placeholder = reactive("")
    
    CSS = """
    Screen {
        background: $background;
    }
    
    #channels-container {
        height: 1fr;
        layout: horizontal;
    }
    
    #input-container {
        dock: bottom;
        height: auto;
        background: $surface;
        border-top: solid #babaff;
        padding: 1;
    }
    
    #input-container Input {
        width: 100%;
        background: $surface;
        color: $text;
        border: solid #babaff;
        height: 3;
    }
    
    Footer {
        background: $panel;
        color: $text;
    }
    
    /* Hide scrollbars for cleaner look */
    RichLog {
        scrollbar-size: 0 0;
        overflow-y: auto;
    }
    
    /* Custom accent color */
    $accent: #babaff;
    """
    
    BINDINGS = [
        Binding("f1", "cycle_channel", "Next Channel", show=True),
        Binding("f2", "toggle_recording", "Record", show=True),
        Binding("f3", "save_clip", "Clip", show=True),
        Binding("f4", "switch_streamers", "Switch", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("ctrl+c", "quit", "Exit", show=True),
    ]
    
    # Constants
    MAX_MESSAGES_PER_PANE = 200
    MAX_VISIBLE_PANES = 4
    
    def __init__(self, channels: List[str], is_authenticated: bool = True, 
                 recording_manager=None, clip_manager=None, username: Optional[str] = None):
        """Initialize the UI."""
        super().__init__()
        self.channels = channels[:self.MAX_VISIBLE_PANES]
        self.is_authenticated = is_authenticated
        self.recording_manager = recording_manager
        self.clip_manager = clip_manager
        self.my_username = username.lower() if username else None
        self.active_channel_index = 0
        
        # Callbacks
        self.send_callback: Optional[Callable] = None
        self.recording_callback: Optional[Callable] = None
        self.clip_callback: Optional[Callable] = None
        self.switch_callback: Optional[Callable] = None
        self.channel_change_callback: Optional[Callable] = None
        
        # Panes dictionary
        self.panes: Dict[str, ChannelPane] = {}
        
        # Status tracking
        self.status_message = ""
        self.status_timestamp = None
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        
        # Channels container
        with Horizontal(id="channels-container"):
            for channel in self.channels:
                pane = ChannelPane(channel, max_messages=self.MAX_MESSAGES_PER_PANE)
                self.panes[channel] = pane
                yield pane
        
        # Input container
        if self.is_authenticated:
            with Container(id="input-container"):
                yield ChatInput(placeholder=f"Type message for #{self.get_active_channel()}...")
        
        # Status bar
        yield StatusBar()
        
        # Footer with keybinds
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Set first channel as active after mounting
        if self.channels and self.channels[0] in self.panes:
            self.panes[self.channels[0]].set_active(True)
        
        self._update_status()
    
    def get_active_channel(self) -> str:
        """Get the currently active channel name."""
        if 0 <= self.active_channel_index < len(self.channels):
            return self.channels[self.active_channel_index]
        return self.channels[0] if self.channels else ""
    
    def add_message(self, message: ChatMessage):
        """Add a message to the appropriate channel pane."""
        if message.channel in self.panes:
            pane = self.panes[message.channel]
            pane.add_message(message, self.my_username)
    
    def set_status(self, message: str):
        """Set status message."""
        import time
        self.status_message = message
        self.status_timestamp = time.time()
        self._update_status()
        
        # Auto-clear after 10 seconds
        self.set_timer(10, self._clear_status_if_old)
    
    def _clear_status_if_old(self):
        """Clear status if it's old."""
        import time
        if self.status_message and self.status_timestamp:
            if time.time() - self.status_timestamp >= 10:
                self.status_message = ""
                self._update_status()
    
    def _update_status(self):
        """Update the status bar."""
        status_bar = self.query_one(StatusBar)
        
        if self.status_message:
            status_bar.set_status(self.status_message)
        else:
            active_channel = self.get_active_channel()
            recording_info = ""
            
            if self.recording_manager:
                for channel in self.channels:
                    if self.recording_manager.is_recording(channel):
                        duration = self.recording_manager.get_recording_info(channel)
                        recording_info = f" | Recording {channel.upper()} {duration}"
            
            status_text = f"Selected: #{active_channel.upper()}{recording_info}"
            status_bar.set_status(status_text)
        
        # Update panes with recording status
        if self.recording_manager:
            for channel in self.channels:
                if channel in self.panes:
                    is_recording = self.recording_manager.is_recording(channel)
                    duration = self.recording_manager.get_recording_info(channel) if is_recording else ""
                    self.panes[channel].set_recording(is_recording, duration)
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if not self.is_authenticated or not self.send_callback:
            return
        
        message = event.value.strip()
        if message:
            # ALWAYS get the current active channel at send time
            active_channel = self.channels[self.active_channel_index]
            # Show which channel we're sending to in the status bar
            self.set_status(f"→ Sending to #{active_channel}: {message[:50]}")
            logger.info(f"[SEND] Active index: {self.active_channel_index}, Channel: {active_channel}, Message: {message}")
            await self.send_callback(active_channel, message)
            event.input.value = ""
    
    def action_cycle_channel(self) -> None:
        """Cycle to next channel."""
        if len(self.channels) <= 1:
            return
        
        # Deactivate current
        current_channel = self.get_active_channel()
        if current_channel in self.panes:
            self.panes[current_channel].set_active(False)
        
        # Move to next
        old_index = self.active_channel_index
        self.active_channel_index = (self.active_channel_index + 1) % len(self.channels)
        
        # Activate new
        new_channel = self.get_active_channel()
        if new_channel in self.panes:
            self.panes[new_channel].set_active(True)
        
        # Debug: Show the switch
        logger.info(f"[TAB] Switched from index {old_index} ({current_channel}) to index {self.active_channel_index} ({new_channel})")
        self.set_status(f"Switched to #{new_channel.upper()} - Messages will go here")
        
        # Update input placeholder using the reactive property
        self.input_placeholder = f"Type message for #{new_channel}..."
        if self.is_authenticated:
            try:
                input_widget = self.query_one(Input)
                # Directly set the placeholder attribute
                input_widget.placeholder = self.input_placeholder
            except Exception as e:
                logger.debug(f"Failed to update placeholder: {e}")
        
        # Notify callback
        if self.channel_change_callback:
            asyncio.create_task(self.channel_change_callback(new_channel))
    
    async def action_toggle_recording(self) -> None:
        """Toggle recording for active channel."""
        if not self.recording_callback:
            return
        
        active_channel = self.get_active_channel()
        is_recording, message = await self.recording_callback(active_channel)
        self.set_status(message)
        self._update_status()
    
    async def action_save_clip(self) -> None:
        """Save a clip of the active channel."""
        if not self.clip_callback:
            return
        
        active_channel = self.get_active_channel()
        success, message = await self.clip_callback(active_channel)
        self.set_status(message)
    
    async def action_switch_streamers(self) -> None:
        """Switch to different streamers."""
        if self.switch_callback:
            await self.switch_callback()
    
    def action_clear_chat(self) -> None:
        """Clear the active channel's chat."""
        active_channel = self.get_active_channel()
        if active_channel in self.panes:
            self.panes[active_channel].clear_messages()
            self.set_status(f"Cleared #{active_channel}")
    
    def set_callbacks(self, send_callback, recording_callback=None, clip_callback=None,
                      switch_callback=None, channel_change_callback=None):
        """Set callback functions."""
        self.send_callback = send_callback
        self.recording_callback = recording_callback
        self.clip_callback = clip_callback
        self.switch_callback = switch_callback
        self.channel_change_callback = channel_change_callback
    
    def stop(self):
        """Stop the UI."""
        try:
            self.exit()
        except Exception as e:
            logger.debug(f"Error stopping UI: {e}")


class SimpleUI:
    """Simple fallback UI (non-interactive)."""
    
    def __init__(self, channels: List[str], is_authenticated: bool = True):
        """Initialize simple UI."""
        self.channels = channels
        self.is_authenticated = is_authenticated
    
    def add_message(self, message: ChatMessage):
        """Display a message."""
        badge = message.get_badge_text()
        prefix = f"{badge} " if badge else ""
        print(f"[#{message.channel}] {prefix}{message.author}: {message.content}")
    
    def set_status(self, message: str):
        """Display status message."""
        print(f"[STATUS] {message}")
    
    def start(self):
        """Start the UI."""
        print("=== Twitch Terminal Viewer ===")
        print(f"Watching: {', '.join(self.channels)}")
        if not self.is_authenticated:
            print("(Read-only mode)")
        print("=" * 40)
    
    def stop(self):
        """Stop the UI."""
        print("\n=== Viewer Closed ===")
    
    async def handle_input(self, key: str, send_callback, recording_callback=None, 
                          clip_callback=None, switch_callback=None, channel_change_callback=None):
        """Handle input (no-op)."""
        pass
