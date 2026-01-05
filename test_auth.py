"""Quick test script to verify Twitch authentication."""
import asyncio
import sys
from config_manager import ConfigManager

async def test_connection():
    """Test Twitch IRC connection."""
    print("Loading config...")
    config_mgr = ConfigManager()
    config = config_mgr.load()
    
    username = config.get('twitch_username')
    token = config.get('twitch_oauth')
    
    print(f"Username: {username}")
    print(f"Token format: {token[:15] if token else 'NONE'}...")
    print(f"Token starts with oauth:: {token.startswith('oauth:') if token else False}")
    
    if not username or not token:
        print("\nERROR: No authentication configured!")
        return
    
    print("\nAttempting connection...")
    try:
        reader, writer = await asyncio.open_connection('irc.chat.twitch.tv', 6667)
        print("✓ Connected to IRC server")
        
        # Send auth
        writer.write(f"PASS {token}\r\n".encode())
        writer.write(f"NICK {username}\r\n".encode())
        writer.write(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
        await writer.drain()
        print("✓ Sent authentication")
        
        # Read responses
        print("\nServer responses:")
        for i in range(10):
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=2.0)
                if line:
                    msg = line.decode('utf-8', errors='ignore').strip()
                    print(f"  {msg}")
                    
                    if 'Login authentication failed' in msg:
                        print("\n✗ AUTHENTICATION FAILED! Token or username is invalid.")
                        break
                    elif 'Welcome' in msg or '001' in msg:
                        print("\n✓ AUTHENTICATION SUCCESSFUL!")
                        break
                else:
                    break
            except asyncio.TimeoutError:
                break
        
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
