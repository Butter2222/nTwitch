"""Terminal UI with split-pane layout for multi-channel chat."""
import asyncio
import logging
from typing import List, Dict, Optional
from collections import deque
from blessed import Terminal
from chat_client import ChatMessage


logger = logging.getLogger(__name__)


class ChannelPane:
    """Represents a single channel pane in the UI."""
    
    def __init__(self, channel: str, max_messages: int = 200):
        """Initialize channel pane."""
        self.channel = channel
        self.messages: deque = deque(maxlen=max_messages)
        self.scroll_offset = 0
    
    def add_message(self, message: ChatMessage):
        """Add a message to the pane."""
        self.messages.append(message)
        self.scroll_offset = 0  # Reset scroll to bottom
    
    def clear(self):
        """Clear all messages."""
        self.messages.clear()
        self.scroll_offset = 0


class MultiChannelUI:
    """Multi-channel terminal UI with split-pane layout."""
    
    def __init__(self, channels: List[str], is_authenticated: bool = True, recording_manager=None, clip_manager=None, username: Optional[str] = None):
        """Initialize the UI."""
        self.term = Terminal()
        self.channels = channels
        self.panes: Dict[str, ChannelPane] = {
            channel: ChannelPane(channel) for channel in channels
        }
        self.active_channel_index = 0
        self.is_authenticated = is_authenticated
        self.input_buffer = ""
        self.running = False
        self.status_message = ""
        self.status_timestamp = None  # Track when status was set
        self.recording_manager = recording_manager
        self.clip_manager = clip_manager
        self._my_username = username.lower() if username else None
        
        # Color codes for user types
        self.colors = {
            'broadcaster': self.term.red,
            'moderator': self.term.green,
            'subscriber': self.term.blue,
            'vip': self.term.magenta,
            'regular': self.term.white
        }
    
    def get_active_channel(self) -> str:
        """Get the currently active channel name."""
        if 0 <= self.active_channel_index < len(self.channels):
            return self.channels[self.active_channel_index]
        return self.channels[0] if self.channels else ""
    
    def cycle_active_channel(self):
        """Cycle to the next channel."""
        if len(self.channels) > 1:
            self.active_channel_index = (self.active_channel_index + 1) % len(self.channels)
    
    def add_message(self, message: ChatMessage):
        """Route message to appropriate channel pane."""
        if message.channel in self.panes:
            self.panes[message.channel].add_message(message)
    
    def set_status(self, message: str):
        """Set status message with timestamp for auto-clear."""
        import time
        self.status_message = message
        self.status_timestamp = time.time()
    
    def render(self):
        """Render the entire UI."""
        # Clear screen properly for stable rendering
        print(self.term.home + self.term.clear, end='', flush=False)
        
        # Calculate dimensions
        term_width = self.term.width
        term_height = self.term.height
        
        # Minimum size check
        if term_width < 120 or term_height < 20:
            self._render_fallback_mode()
            return
        
        # Calculate pane dimensions
        num_panes = min(len(self.channels), 4)  # Max 4 visible panes
        pane_width = term_width // num_panes
        chat_height = term_height - 5  # Reserve 5 lines for input, status, and keybinds
        
        # Render each channel pane
        for i, channel in enumerate(self.channels[:num_panes]):
            x_offset = i * pane_width
            self._render_pane(channel, x_offset, 0, pane_width, chat_height)
        
        # Render input area (now with 4 lines instead of 3)
        self._render_input(term_height - 4)
    
    def _render_pane(self, channel: str, x: int, y: int, width: int, height: int):
        """Render a single channel pane."""
        pane = self.panes[channel]
        
        # Build header with recording status and active indicator
        channel_upper = channel.upper()
        
        # Check if this is the active channel
        is_active = (channel == self.get_active_channel())
        active_indicator = "★ " if is_active else ""
        
        # Check if recording
        recording_indicator = ""
        if self.recording_manager and self.recording_manager.is_recording(channel):
            duration = self.recording_manager.get_recording_info(channel)
            recording_indicator = f" [REC {duration}]"
        
        header = f" {active_indicator}>>> {channel_upper}{recording_indicator} <<<"
        
        # Truncate if too long
        if len(header) > width - 2:
            header = f"{active_indicator}#{channel_upper}"[:width-2]
        
        # Center header
        padding = (width - len(header)) // 2
        header_line = " " * padding + header + " " * (width - padding - len(header))
        
        # Use bright colors for visibility
        if self.recording_manager and self.recording_manager.is_recording(channel):
            # Red if recording
            color_func = self.term.bright_red
        elif is_active:
            # Yellow if active (ready to record or send messages)
            color_func = self.term.bright_yellow
        else:
            # Cyan for inactive channels
            color_func = self.term.bright_cyan
        
        with self.term.location(x, y):
            print(color_func(self.term.bold(header_line[:width])) + self.term.clear_eol)
        
        # Simple separator
        with self.term.location(x, y + 1):
            print(("-" * width) + self.term.clear_eol)
        
        # Draw messages (simple truncation - stable rendering)
        visible_messages = list(pane.messages)[-(height - 2):]  # -2 for header and separator
        
        for i, msg in enumerate(visible_messages):
            line_y = y + 2 + i
            formatted = self._format_message(msg, width - 2, include_channel=False)
            with self.term.location(x + 1, line_y):
                print(formatted + self.term.clear_eol)
        
        # Clear any remaining lines in this pane
        for i in range(len(visible_messages), height - 2):
            line_y = y + 2 + i
            with self.term.location(x + 1, line_y):
                print(self.term.clear_eol)
    
    def _format_and_wrap_message(self, message: ChatMessage, max_width: int, include_channel: bool = False) -> List[str]:
        """Format and wrap a chat message across multiple lines."""
        # Get badge text
        badge = message.get_badge_text()
        
        # Determine username color
        username_color = None
        if message.is_broadcaster():
            username_color = self.term.bright_red
        elif message.is_moderator():
            username_color = self.term.bright_green
        elif message.color:
            username_color = self._hex_to_term_color(message.color)
        else:
            username_color = self.term.white
        
        # Add channel tag if requested
        channel_tag = ""
        if include_channel:
            is_active = (message.channel == self.get_active_channel())
            channel_name = message.channel[:4].upper()
            if is_active:
                channel_tag = f"{self.term.bright_yellow}[{channel_name}]{self.term.normal} "
            else:
                channel_tag = f"[{channel_name}] "
        
        # Build formatted header
        prefix = f"{badge} " if badge else ""
        author_part = f"{username_color}{message.author}{self.term.normal}"
        
        # Calculate visible header length
        visible_channel_len = len(message.channel[:4]) + 3 if include_channel else 0
        visible_prefix_len = len(prefix)
        visible_author_len = len(message.author)
        visible_header_len = visible_channel_len + visible_prefix_len + visible_author_len + 2  # +2 for ": "
        
        # First line with header
        first_line_space = max_width - visible_header_len
        
        # Handle mentions
        content = message.content
        if self.is_authenticated and hasattr(self, '_my_username') and self._my_username:
            mention = f"@{self._my_username}"
            if mention.lower() in content.lower():
                import re
                content = re.sub(
                    f"({re.escape(mention)})", 
                    f"{self.term.bright_yellow}\\1{self.term.normal}",
                    content,
                    flags=re.IGNORECASE
                )
        
        # Word wrap the content
        words = message.content.split()  # Use original for splitting
        lines = []
        current_line = []
        current_length = 0
        is_first_line = True
        
        for word in words:
            word_len = len(word)
            space_len = 1 if current_line else 0
            
            # Check if word fits on current line
            line_space = first_line_space if is_first_line else max_width - 2  # -2 for continuation indent
            
            if current_length + space_len + word_len <= line_space:
                current_line.append(word)
                current_length += space_len + word_len
            else:
                # Save current line
                if current_line:
                    line_text = ' '.join(current_line)
                    if is_first_line:
                        lines.append(f"{channel_tag}{prefix}{author_part}: {line_text}")
                        is_first_line = False
                    else:
                        lines.append(f"  {line_text}")  # Continuation indent
                    current_line = []
                    current_length = 0
                
                # Start new line with current word
                current_line.append(word)
                current_length = word_len
        
        # Add remaining words
        if current_line:
            line_text = ' '.join(current_line)
            if is_first_line:
                lines.append(f"{channel_tag}{prefix}{author_part}: {line_text}")
            else:
                lines.append(f"  {line_text}")
        
        # If no lines were created (empty message), create one
        if not lines:
            lines.append(f"{channel_tag}{prefix}{author_part}: ")
        
        return lines
    
    def _format_message(self, message: ChatMessage, max_width: int, include_channel: bool = False) -> str:
        """Format a chat message with colors."""
        # Get badge text with role-based color (meaningful!)
        badge = message.get_badge_text()
        
        # Determine username color
        # Priority: Role-based color for special roles, then Twitch user color, then default
        username_color = None
        
        if message.is_broadcaster():
            # Broadcaster: Always bright red (most important role)
            username_color = self.term.bright_red
        elif message.is_moderator():
            # Moderator: Always green (authority figure)
            username_color = self.term.bright_green
        elif message.color:
            # Regular user with custom Twitch color: Use their chosen color
            username_color = self._hex_to_term_color(message.color)
        elif message.is_subscriber():
            # Subscriber without custom color: Purple
            username_color = self.term.bright_magenta
        elif message.is_vip():
            # VIP without custom color: Magenta
            username_color = self.term.magenta
        else:
            # Default: White
            username_color = self.term.white
        
        # Add channel tag if requested - ORANGE if active channel!
        channel_tag = ""
        if include_channel:
            is_active = (message.channel == self.get_active_channel())
            channel_name = message.channel[:4].upper()
            if is_active:
                # Active channel = ORANGE
                channel_tag = f"{self.term.bright_yellow}[{channel_name}]{self.term.normal} "
            else:
                # Inactive channel = default color
                channel_tag = f"[{channel_name}] "
        
        # Build formatted message
        prefix = f"{badge} " if badge else ""
        author_part = f"{username_color}{message.author}{self.term.normal}"
        
        # Check for mentions - highlight @username
        content = message.content
        # Only check if we're authenticated (know our username)
        if self.is_authenticated and hasattr(self, '_my_username'):
            mention = f"@{self._my_username}"
            if mention.lower() in content.lower():
                # Highlight mentions in bright yellow
                import re
                content = re.sub(
                    f"({re.escape(mention)})", 
                    f"{self.term.bright_yellow}\\1{self.term.normal}",
                    content,
                    flags=re.IGNORECASE
                )
        
        # Calculate VISIBLE lengths (without ANSI codes)
        # For channel tag: either [CHAN] (6 chars) + space = 7, regardless of color
        visible_channel_len = len(message.channel[:4]) + 3 if include_channel else 0  # [XXXX] + space
        visible_prefix_len = len(prefix)
        visible_author_len = len(message.author)
        
        # Calculate how much space we have for the message content
        visible_header_len = visible_channel_len + visible_prefix_len + visible_author_len + 2  # +2 for ": "
        
        # Get visible length of content (without ANSI codes)
        visible_content_len = len(message.content)  # Use original for length calc
        
        # Truncate message content if needed
        if visible_header_len + visible_content_len > max_width:
            content_space = max_width - visible_header_len - 3  # -3 for "..."
            if content_space > 0:
                content = message.content[:content_space] + "..."
            else:
                content = message.content[:max(0, max_width - visible_header_len)]
        
        return f"{channel_tag}{prefix}{author_part}: {content}"
    
    def _hex_to_term_color(self, hex_color: str):
        """Convert Twitch hex color to closest terminal color."""
        if not hex_color or not hex_color.startswith('#'):
            return self.term.white
        
        try:
            # Remove # and convert to RGB
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Map to closest bright terminal color for better visibility
            # These thresholds create good visual variety
            if r > 200 and g < 100 and b < 100:
                return self.term.bright_red
            elif r < 100 and g > 200 and b < 100:
                return self.term.bright_green
            elif r < 100 and g < 100 and b > 200:
                return self.term.bright_blue
            elif r > 200 and g > 200 and b < 100:
                return self.term.bright_yellow
            elif r > 200 and g < 100 and b > 200:
                return self.term.bright_magenta
            elif r < 100 and g > 200 and b > 200:
                return self.term.bright_cyan
            elif r > 150:  # Orangish colors
                return self.term.yellow
            elif g > 150:  # Greenish colors
                return self.term.green
            elif b > 150:  # Bluish colors
                return self.term.blue
            elif r > 100 and g > 100:  # Brown/tan
                return self.term.yellow
            else:
                return self.term.white
                
        except (ValueError, IndexError):
            return self.term.white
    
    def _render_input(self, y: int):
        """Render input area at the bottom with 4 lines total."""
        import time
        active_channel = self.get_active_channel()
        
        # Auto-clear ALL status messages after 5 seconds
        if self.status_message and self.status_timestamp:
            elapsed = time.time() - self.status_timestamp
            if elapsed > 5.0:
                self.status_message = ""
                self.status_timestamp = None
        
        # Line 1: Separator
        with self.term.location(0, y):
            print("═" * self.term.width)
        
        # Line 2: Active channel indicator with recording status
        with self.term.location(0, y + 1):
            if self.is_authenticated:
                # Check if any channel is recording and show timer
                recording_info = ""
                if self.recording_manager:
                    for channel in self.channels:
                        if self.recording_manager.is_recording(channel):
                            duration = self.recording_manager.get_recording_info(channel)
                            recording_info = f"  |  {self.term.bright_red}Recording {channel.upper()} {duration}{self.term.normal}"
                
                status_line = f"SELECTED: {active_channel.upper()} (Press [Tab] to switch, [F2] to record THIS channel){recording_info}"
            else:
                status_line = "(Read-only mode - Configure OAuth to chat)"
            print(self.term.bold(self.term.yellow(status_line)))
        
        # Line 3: Input buffer or status message
        with self.term.location(0, y + 2):
            if self.status_message:
                # Show status message in yellow
                print(self.term.yellow(self.status_message[:self.term.width]))
            elif self.is_authenticated and self.input_buffer:
                # Show input buffer when typing
                print(f"> {self.input_buffer}_"[:self.term.width])
            else:
                # Show empty input prompt
                print("> "[:self.term.width])
        
        # Line 4: ALWAYS VISIBLE KEYBINDS at the very bottom
        with self.term.location(0, y + 3):
            if self.is_authenticated:
                keybinds = "[Tab] Select  [F2] Record  [F3] Clip  [F4] Switch  [Enter] Send  [Ctrl+L] Clear  [Ctrl+C] Exit"
            else:
                keybinds = "[Tab] Select  [F2] Record  [F3] Clip  [F4] Switch  [Ctrl+L] Clear  [Ctrl+C] Exit"
            # Always show keybinds in cyan to make them stand out
            print(self.term.cyan(keybinds[:self.term.width]))
    
    def _render_fallback_mode(self):
        """Render simplified UI when terminal is too small."""
        print(self.term.home + self.term.clear)
        print(self.term.bold(self.term.red("Terminal too small!")))
        print(f"Minimum size: 120x20")
        print(f"Current size: {self.term.width}x{self.term.height}")
        print("\nPlease resize your terminal window.")
    
    async def handle_input(self, key: str, send_callback, recording_callback=None, clip_callback=None, switch_callback=None, channel_change_callback=None):
        """Handle keyboard input."""
        # Tab key - Select Channel
        if key == '\t':
            self.cycle_active_channel()
            if channel_change_callback:
                await channel_change_callback(self.get_active_channel())
            self.render()
        # Function key handling (Unix and Windows)
        elif key == '\x1bOQ' or key == 'KEY_F(2)' or key == 'KEY_F2':  # F2 key - toggle recording
            if recording_callback:
                active_channel = self.get_active_channel()
                is_recording, message = await recording_callback(active_channel)
                self.set_status(message)
                self.render()
        elif key == '\x1bOR' or key == 'KEY_F(3)' or key == 'KEY_F3':  # F3 key - save clip
            if clip_callback:
                active_channel = self.get_active_channel()
                success, message = await clip_callback(active_channel)
                self.set_status(message)
                self.render()
        elif key == '\x1bOS' or key == 'KEY_F(4)' or key == 'KEY_F4':  # F4 key - switch streamers
            if switch_callback:
                await switch_callback()
                return  # Exit after switching
        elif key == '\n' or key == '\r':  # Enter key
            if self.input_buffer and self.is_authenticated:
                # Send message
                active_channel = self.get_active_channel()
                await send_callback(active_channel, self.input_buffer)
                
                # Clear input
                self.input_buffer = ""
                self.render()
        elif key == '\x7f':  # Backspace
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                self.render()
        elif key == '\x0c':  # Ctrl+L
            # Clear active channel
            active_channel = self.get_active_channel()
            if active_channel in self.panes:
                self.panes[active_channel].clear()
                self.set_status(f"Cleared #{active_channel}")
                self.render()
        elif len(key) == 1 and key.isprintable():
            # Regular character
            if len(self.input_buffer) < 500:  # Twitch message limit
                self.input_buffer += key
                self.render()
    
    def start(self):
        """Start the UI."""
        self.running = True
        print(self.term.enter_fullscreen())
        print(self.term.hide_cursor())
        self.render()
    
    def stop(self):
        """Stop the UI and restore terminal."""
        self.running = False
        print(self.term.exit_fullscreen())
        print(self.term.normal_cursor())
        print(self.term.clear())


class SimpleUI:
    """Simple non-interactive UI for displaying chat (fallback)."""
    
    def __init__(self, channels: List[str], is_authenticated: bool = True):
        """Initialize simple UI."""
        self.channels = channels
        self.is_authenticated = is_authenticated
        self.term = Terminal()
    
    def add_message(self, message: ChatMessage):
        """Display a message."""
        badge = message.get_badge_text()
        prefix = f"{badge} " if badge else ""
        print(f"[#{message.channel}] {prefix}{message.author}: {message.content}")
    
    def set_status(self, message: str):
        """Display status message."""
        print(self.term.yellow(f"[STATUS] {message}"))
    
    def render(self):
        """Render (no-op for simple UI)."""
        pass
    
    def start(self):
        """Start the UI."""
        print(self.term.clear())
        print(self.term.bold("=== Twitch Terminal Viewer ==="))
        print(f"Watching: {', '.join(self.channels)}")
        if not self.is_authenticated:
            print(self.term.yellow("(Read-only mode)"))
        print("=" * 40)
        print()
    
    def stop(self):
        """Stop the UI."""
        print("\n" + self.term.bold("=== Viewer Closed ==="))
    
    async def handle_input(self, key: str, send_callback, recording_callback=None, clip_callback=None, switch_callback=None, channel_change_callback=None):
        """Handle input (no-op for simple UI)."""
        pass
