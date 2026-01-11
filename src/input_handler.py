"""Cross-platform keyboard input handler."""
import sys
import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class InputHandler:
    """Cross-platform non-blocking keyboard input handler."""
    
    def __init__(self):
        """Initialize input handler based on platform."""
        self.platform = sys.platform
        self.running = False
        
    async def start_input_loop(self, 
                               callback: Callable[[str], Awaitable[None]],
                               stop_callback: Callable[[], None]):
        """
        Start non-blocking input loop.
        
        Args:
            callback: Async function to call with each key press
            stop_callback: Function to call when Ctrl+C is pressed
        """
        self.running = True
        
        if self.platform == 'win32':
            await self._windows_input_loop(callback, stop_callback)
        else:
            await self._unix_input_loop(callback, stop_callback)
    
    async def _unix_input_loop(self, callback, stop_callback):
        """Unix/Linux/macOS input loop using termios."""
        try:
            import tty
            import termios
            import select
            
            # Save terminal settings
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            
            try:
                tty.setraw(fd)
                
                while self.running:
                    # Check if input is available
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        
                        # Handle Ctrl+C
                        if ord(key) == 3:  # Ctrl+C
                            stop_callback()
                            break
                        
                        # Pass to callback
                        await callback(key)
                    
                await asyncio.sleep(0.01)  # 1ms delay for instant input response
                    
            finally:
                # Restore terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
        except Exception as e:
            logger.error(f"Error in Unix input loop: {e}")
    
    async def _windows_input_loop(self, callback, stop_callback):
        """Windows input loop using msvcrt."""
        try:
            import msvcrt
            
            while self.running:
                # Check if key is available
                if msvcrt.kbhit():
                    # Get the key
                    key_bytes = msvcrt.getch()
                    
                    # Handle special keys
                    if key_bytes == b'\x03':  # Ctrl+C
                        stop_callback()
                        break
                    elif key_bytes == b'\t':  # Tab
                        await callback('\t')
                    elif key_bytes == b'\r':  # Enter
                        await callback('\n')
                    elif key_bytes == b'\x08':  # Backspace
                        await callback('\x7f')
                    elif key_bytes == b'\x0c':  # Ctrl+L
                        await callback('\x0c')
                    elif key_bytes == b'\xe0' or key_bytes == b'\x00':
                        # Special key (arrow, function key, etc.)
                        # Read the second byte for the actual key code
                        if msvcrt.kbhit():
                            second_byte = msvcrt.getch()
                            # Map function keys
                            if second_byte == b';':  # F1
                                await callback('KEY_F1')
                            elif second_byte == b'<':  # F2
                                await callback('KEY_F2')
                            elif second_byte == b'=':  # F3
                                await callback('KEY_F3')
                            elif second_byte == b'>':  # F4
                                await callback('KEY_F4')
                            # Ignore other special keys (arrows, etc.)
                    else:
                        # Regular character
                        try:
                            char = key_bytes.decode('utf-8', errors='ignore')
                            if char and char.isprintable():
                                await callback(char)
                        except:
                            pass
                
                await asyncio.sleep(0.05)
                
        except Exception as e:
            logger.error(f"Error in Windows input loop: {e}")
    
    def stop(self):
        """Stop the input loop."""
        self.running = False


class SimpleInputHandler:
    """Simple blocking input handler for fallback."""
    
    def __init__(self):
        """Initialize simple handler."""
        self.running = False
    
    async def start_input_loop(self, 
                               callback: Callable[[str], Awaitable[None]],
                               stop_callback: Callable[[], None]):
        """
        Start simple blocking input loop.
        
        Note: This doesn't support character-by-character input,
        only line-by-line. Used as fallback.
        """
        self.running = True
        
        try:
            while self.running:
                # This will block until Enter is pressed
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, input
                    )
                    
                    # Process each character
                    for char in line:
                        await callback(char)
                    
                    # Send Enter
                    await callback('\n')
                    
                except EOFError:
                    break
                except KeyboardInterrupt:
                    stop_callback()
                    break
                    
        except Exception as e:
            logger.error(f"Error in simple input loop: {e}")
    
    def stop(self):
        """Stop the input loop."""
        self.running = False
