"""Twitch chat client for multi-channel support."""
import asyncio
import logging
import re
from typing import List, Dict, Callable, Optional
from collections import deque


logger = logging.getLogger(__name__)


class ChatMessage:
    """Represents a parsed chat message."""
    
    def __init__(self, channel: str, author: str, content: str, 
                 color: Optional[str] = None, badges: Optional[List[str]] = None):
        """Initialize chat message."""
        self.channel = channel.lstrip('#')
        self.author = author
        self.content = content
        self.color = color
        self.badges = badges or []
    
    def is_broadcaster(self) -> bool:
        """Check if message author is the broadcaster."""
        return 'broadcaster' in self.badges
    
    def is_moderator(self) -> bool:
        """Check if message author is a moderator."""
        return 'moderator' in self.badges
    
    def is_subscriber(self) -> bool:
        """Check if message author is a subscriber."""
        return any(b.startswith('subscriber') for b in self.badges)
    
    def is_vip(self) -> bool:
        """Check if message author is a VIP."""
        return 'vip' in self.badges
    
    def get_badge_text(self) -> str:
        """Get text representation of badges."""
        if self.is_broadcaster():
            return "[STREAMER]"
        elif self.is_moderator():
            return "[MOD]"
        return ""


class TwitchIRCClient:
    """Twitch IRC client using raw WebSocket connection."""
    
    def __init__(self, channels: List[str], message_callback: Callable[[ChatMessage], None],
                 token: Optional[str] = None, username: Optional[str] = None):
        """Initialize IRC client."""
        self.channels = [c.lstrip('#').lower() for c in channels]
        self.message_callback = message_callback
        self.token = token
        self.username = username.lower() if username else None
        self.is_authenticated = bool(token and username)
        self._running = False
        self._reader = None
        self._writer = None
        self._task = None
        self._last_message_time = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
    
    async def connect(self):
        """Connect to Twitch IRC."""
        try:
            # Connect to Twitch IRC with optimized settings
            self._reader, self._writer = await asyncio.open_connection(
                'irc.chat.twitch.tv', 6667
            )
            
            # Disable Nagle's algorithm for lower latency
            sock = self._writer.get_extra_info('socket')
            if sock:
                import socket
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            if self.is_authenticated:
                # Authenticated login
                self._writer.write(f"PASS {self.token}\r\n".encode())
                self._writer.write(f"NICK {self.username}\r\n".encode())
                # Request capabilities for badges, colors, etc.
                self._writer.write(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
                logger.info(f"Connecting as authenticated user: {self.username}")
            else:
                # Anonymous login
                import random
                anon_user = f"justinfan{random.randint(100000, 999999)}"
                self._writer.write(f"NICK {anon_user}\r\n".encode())
                logger.info(f"Connecting anonymously as: {anon_user}")
            
            # Join all channels
            for channel in self.channels:
                self._writer.write(f"JOIN #{channel}\r\n".encode())
                logger.info(f"Joining channel: #{channel}")
            
            await self._writer.drain()
            
            self._running = True
            
            # Start reading messages
            self._task = asyncio.create_task(self._read_messages())
            
            logger.info("Connected to Twitch IRC")
            
        except Exception as e:
            logger.error(f"Error connecting to IRC: {e}")
            raise
    
    async def _read_messages(self):
        """Read messages from IRC connection with timeout and reconnection."""
        import time
        self._last_message_time = time.time()
        ping_interval = 60  # Send PING every 60 seconds
        last_ping_time = time.time()
        loop_count = 0
        
        logger.info("Message read loop started")
        
        try:
            while self._running and self._reader:
                loop_count += 1
                if loop_count % 100 == 0:
                    logger.info(f"Read loop still alive (iteration {loop_count})")
                try:
                    # Check if we need to send a keepalive PING
                    current_time = time.time()
                    if current_time - last_ping_time > ping_interval:
                        if self._writer:
                            try:
                                self._writer.write(b"PING :keepalive\r\n")
                                await self._writer.drain()
                                last_ping_time = current_time
                                logger.debug("Sent keepalive PING")
                            except Exception as e:
                                logger.error(f"Failed to send keepalive: {e}")
                                break
                    
                    # Read with minimal timeout for instant message delivery
                    line = await asyncio.wait_for(self._reader.readline(), timeout=0.1)
                    
                    if not line:
                        logger.warning("Connection closed by server")
                        break
                    
                    # Update last message time
                    self._last_message_time = time.time()
                    
                    message = line.decode('utf-8', errors='ignore').strip()
                    
                    if not message:
                        continue
                    
                    # Log ALL received messages for debugging
                    logger.debug(f"<< {message[:200]}")  # Log first 200 chars
                    
                    # Handle PING
                    if message.startswith('PING'):
                        pong = message.replace('PING', 'PONG')
                        if self._writer:
                            self._writer.write(f"{pong}\r\n".encode())
                            await self._writer.drain()
                            logger.debug("Responded to PING")
                        continue
                    
                    # Log connection messages
                    if ':tmi.twitch.tv' in message:
                        logger.info(f"Server message: {message}")
                    
                    # Parse PRIVMSG
                    if 'PRIVMSG' in message:
                        logger.debug(f"Parsing PRIVMSG: {message[:100]}")
                        self._parse_message(message)
                        
                except asyncio.TimeoutError:
                    # Timeout is normal, just continue
                    continue
                            
        except Exception as e:
            if self._running:
                logger.error(f"Error in message loop: {e}", exc_info=True)
                # Try to notify via callback if possible
                try:
                    error_msg = ChatMessage(
                        channel=self.channels[0] if self.channels else "system",
                        author="SYSTEM",
                        content=f"Chat error: {str(e)}",
                        color="#FF0000"
                    )
                    if self.message_callback:
                        self.message_callback(error_msg)
                except:
                    pass
        finally:
            if self._running:
                logger.info("Message loop ended, attempting reconnection...")
                await self._attempt_reconnect()
    
    async def _attempt_reconnect(self):
        """Attempt to reconnect to IRC."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            return
        
        self._reconnect_attempts += 1
        wait_time = min(2 ** self._reconnect_attempts, 30)  # Exponential backoff, max 30s
        
        logger.info(f"Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts} in {wait_time}s...")
        await asyncio.sleep(wait_time)
        
        try:
            # Close old connection
            if self._writer:
                try:
                    self._writer.close()
                    await self._writer.wait_closed()
                except:
                    pass
            
            # Reconnect
            await self.connect()
            self._reconnect_attempts = 0  # Reset on successful connection
            logger.info("Reconnection successful!")
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            await self._attempt_reconnect()  # Try again
    
    def _parse_message(self, raw_message: str):
        """Parse IRC PRIVMSG with tags."""
        try:
            # Split tags from message
            tags = {}
            message_part = raw_message
            
            if raw_message.startswith('@'):
                # Parse tags
                tag_end = raw_message.find(' :')
                if tag_end > 0:
                    tag_string = raw_message[1:tag_end]
                    for tag in tag_string.split(';'):
                        if '=' in tag:
                            key, value = tag.split('=', 1)
                            tags[key] = value
                    message_part = raw_message[tag_end + 1:]
            
            # Parse message: :username!username@username.tmi.twitch.tv PRIVMSG #channel :message
            parts = message_part.split('PRIVMSG', 1)
            if len(parts) != 2:
                return
            
            # Extract username
            user_part = parts[0].strip()
            if user_part.startswith(':'):
                username = user_part.split('!')[0][1:]
            else:
                username = tags.get('display-name', 'unknown')
            
            # Extract channel and message
            rest = parts[1].strip()
            channel_end = rest.find(' :')
            if channel_end == -1:
                return
            
            channel = rest[:channel_end].lstrip('#')
            content = rest[channel_end + 2:]
            
            # Extract badges from tags
            badges = []
            if 'badges' in tags and tags['badges']:
                badge_list = tags['badges'].split(',')
                badges = [b.split('/')[0] for b in badge_list]
            
            # Extract color from tags
            color = tags.get('color')
            
            # Create chat message
            chat_msg = ChatMessage(
                channel=channel,
                author=username,
                content=content,
                color=color,
                badges=badges
            )
            
            if self.message_callback:
                self.message_callback(chat_msg)
                
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
    
    async def send_message(self, channel: str, content: str):
        """Send a message to a channel."""
        if not self.is_authenticated:
            logger.warning("Cannot send messages in anonymous mode")
            return
        
        try:
            channel = channel.lstrip('#')
            message = f"PRIVMSG #{channel} :{content}\r\n"
            if self._writer:
                self._writer.write(message.encode())
                await self._writer.drain()
                logger.info(f"Sent message to #{channel}: {content}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    def is_running(self) -> bool:
        """Check if client is running."""
        return self._running
    
    async def close_connection(self):
        """Close the connection."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing writer: {e}")


class ChatManager:
    """Manages chat connections and message routing."""
    
    def __init__(self, channels: List[str], message_callback: Callable[[ChatMessage], None],
                 token: Optional[str] = None, username: Optional[str] = None):
        """Initialize chat manager."""
        self.channels = channels
        self.message_callback = message_callback
        self.token = token
        self.username = username
        self.client: Optional[TwitchIRCClient] = None
        self.is_authenticated = bool(token and username)
    
    async def connect(self):
        """Connect to Twitch chat."""
        self.client = TwitchIRCClient(
            channels=self.channels,
            message_callback=self.message_callback,
            token=self.token,
            username=self.username
        )
        await self.client.connect()
    
    async def send_message(self, channel: str, content: str):
        """Send a message to a channel."""
        if self.client:
            await self.client.send_message(channel, content)
    
    async def disconnect(self):
        """Disconnect from chat."""
        if self.client:
            await self.client.close_connection()
