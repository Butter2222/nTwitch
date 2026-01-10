# Twitch Terminal Viewer

A terminal-based Twitch viewer that streams video via VLC and displays chat in a split-pane interface.

## Features

- Multi-channel video streaming (up to 4 channels simultaneously)
- Split-pane terminal UI showing all channel chats
- Channel recording with built-in timer
- Press F1 to switch active channel
- Chat restriction detection (bans, timeouts, follower-only mode, etc.)
- Color-coded users (Streamers, Mods, Subs, VIPs)
- Ad-free streaming via Streamlink
- Anonymous mode for read-only chat

## Requirements

- Python 3.8+
- VLC Media Player
- Streamlink (installed via pip)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run setup wizard
python twitch_viewer.py --setup
```

The setup wizard will configure VLC path, check Streamlink, and optionally set up Twitch authentication.

## Quick Start

```bash
python twitch_viewer.py
```

Enter channel names when prompted (comma-separated for multiple channels).

## Keyboard Controls

- F1 - Switch/cycle active channel
- F2 - Toggle recording for active channel
- F3 - Save 10-minute clip of active channel
- F4 - Switch to different streamers
- Enter - Send message to active channel
- Ctrl+L - Clear active channel's chat
- Ctrl+C - Exit application

## Command-Line Options

```bash
# Specify channels directly
python twitch_viewer.py --channels xqc,hasanabi

# Set video quality
python twitch_viewer.py --channels xqc --quality 720p60

# Video only (no chat)
python twitch_viewer.py --channels xqc --no-chat

# Anonymous mode (read-only)
python twitch_viewer.py --channels xqc --anon

# Re-run setup
python twitch_viewer.py --setup
```

## Stream Quality Options

- `best` - Highest available (default, 6-8 Mbps per stream)
- `1080p60` - 1080p 60fps
- `720p60` - 720p 60fps (recommended for 3+ streams)
- `720p` - 720p 30fps
- `480p` - 480p
- `360p` - 360p

## Recording Streams

1. Press F1 to select the channel you want to record
2. Press F2 to start recording
3. Press F2 again to stop recording
4. Recordings saved to: `~/Videos/TwitchRecordings/CHANNEL/`

Recording status is shown in the channel header: `[REC 00:05]`

## Clipping

1. Press F1 to select the channel
2. Press F3 to save a 10-minute clip
3. Clips saved to: `~/Videos/TwitchClips/`

The app maintains a 10-minute rolling buffer for each active channel.

## Terminal UI Layout

```
┌─────────────────┬─────────────────┬─────────────────┐
│ >>> XQC <<<     │  >>> HASAN <<<  │  >>> POKI <<<   │
├─────────────────┼─────────────────┼─────────────────┤
│ [XQC] msg...    │ [HAS] msg...    │ [POKI] msg...   │
│                 │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
Selected: #XQC | Recording XQC 1:32
> Type message for #xqc...
[F1] Next Channel [F2] Record [F3] Clip [F4] Switch [Ctrl+L] Clear [Ctrl+C] Exit
```

Minimum terminal size: 120 columns x 20 rows

## Configuration

Configuration stored at: `~/.twitch-terminal-config.json`

```json
{
  "vlc_path": "C:/Program Files/VideoLAN/VLC/vlc.exe",
  "twitch_username": "your_username",
  "twitch_oauth": "oauth:your_token_here",
  "streamlink_quality": "best",
  "chat_colors_enabled": true,
  "recording_path": "C:/Users/You/Videos/TwitchRecordings"
}
```

## Getting OAuth Token

1. Visit: https://twitchtokengenerator.com/
2. Select "Bot Chat Token" or "Custom Scopes"
3. Authorize the application
4. Copy the "Access Token"
5. Paste during setup (setup will add `oauth:` prefix automatically)

## Chat Restrictions

The app automatically detects and displays chat restrictions:

- Permanent bans
- Account suspensions
- Timeouts
- Followers-only mode
- Subscribers-only mode
- Slow mode
- Emote-only mode
- Rate limiting
- Duplicate message blocking

Restriction messages appear in red in the chat window.

## Troubleshooting

### Streamlink Not Found
```bash
pip install streamlink
```

### VLC Not Found
Run setup and specify VLC path manually:
```bash
python twitch_viewer.py --setup
```

### Streams Failing to Launch
- Check if channel is live
- Verify internet connection
- Test manually: `streamlink twitch.tv/CHANNEL best`

### Terminal Too Small
Resize to at least 120x20 or reduce number of channels.

### Multiple Streams Stopping
Reduce quality to lower bandwidth usage:
```bash
python twitch_viewer.py --channels xqc,hasan,poki --quality 720p60
```

Bandwidth requirements:
- 1 stream at best: 6-8 Mbps
- 3 streams at best: 18-24 Mbps
- 3 streams at 720p60: 12-15 Mbps

## Building Executable

### Windows

```bash
build.bat
```

Creates `dist/TwitchViewer.exe` (15-20 MB)

Note: VLC and Streamlink must still be installed on target system.

## Platform Support

- Windows: Fully supported (Windows Terminal or PowerShell recommended)
- macOS: Fully supported (iTerm2 or Terminal.app)
- Linux: Fully supported (any modern terminal)

## Performance

- Memory: 50-100 MB per channel
- CPU: Minimal (VLC handles decoding)
- Network: Varies by quality
- Recommended max: 3-5 channels

## Known Limitations

- Max 4 visible channel panes
- Text-only chat (Twitch emotes won't display as images)
- Live streams only (no VODs)
- Twitch rate limiting: 20 messages per 30 seconds

## Logs

Application logs: `twitch_viewer.log`

View live:
```bash
tail -f twitch_viewer.log
```

## Credits

- Streamlink: https://streamlink.github.io/
- Textual: https://textual.textualize.io/
- VLC Media Player: https://www.videolan.org/

## License

MIT License

## Disclaimer

This application is not affiliated with Twitch Interactive, Inc. Use at your own risk and respect Twitch's Terms of Service.
