# Twitch Terminal Viewer

A terminal-based Twitch viewer that streams video via VLC and displays chat in a terminal interface.

## Features

- Multi-channel video streaming (up to 5 channels simultaneously)
- Split-pane terminal UI showing all channel chats
- Channel recording with built-in timer
- Press Tab to switch active channel
- Anonymous mode for read-only chat
- Color-coded users (Streamers, Mods, Subs, VIPs)
- Ad-free streaming via Streamlink

## Requirements

- Python 3.8+
- VLC Media Player ([Download](https://www.videolan.org/vlc/))
- Streamlink (installed via pip)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Setup

```bash
python twitch_viewer.py --setup
```

The setup wizard will configure VLC path, check Streamlink, and optionally set up Twitch authentication.

### 3. Launch Viewer

```bash
python twitch_viewer.py
```

Enter channel name(s) when prompted:
```
> xqc, hasanabi, pokimane
```

## Keyboard Controls

- **Tab** - Select/cycle through channels
- **F2** - Toggle recording for selected channel
- **F3** - Save 10-minute clip of selected channel
- **F4** - Switch to different streamers
- **Enter** - Send message to selected channel
- **Ctrl+L** - Clear selected channel's chat
- **Ctrl+C** - Exit application

## Command-Line Options

```bash
# Specify channels directly
python twitch_viewer.py --channels xqc,hasanabi

# Set video quality
python twitch_viewer.py --channels xqc --quality 720p60

# Video only (no chat)
python twitch_viewer.py --channels xqc --no-chat

# Anonymous mode
python twitch_viewer.py --channels xqc --anon

# Re-run setup
python twitch_viewer.py --setup
```

## Stream Quality Options

- `best` - Highest available (default, ~6-8 Mbps per stream)
- `1080p60` - 1080p 60fps
- `720p60` - 720p 60fps (recommended for 3+ streams)
- `720p` - 720p 30fps
- `480p` - 480p
- `360p` - 360p

## Recording Streams

1. Press **Tab** to select the channel you want to record
2. Press **R** to start recording
3. Press **R** again to stop recording
4. Recordings saved to: `~/Videos/TwitchRecordings/CHANNEL/`

Recording status shown in:
- Channel header: `[REC 00:05]`
- Bottom status: `Recording CHANNEL 1:32`

## Terminal UI Layout

```
┌───────────────┬───────────────┬───────────────┐
│ ★ >>> XQC <<< │  >>> HASAN <<<│  >>> POKI <<< │  ← Yellow star = selected
├───────────────┼───────────────┼───────────────┤
│ [XQC] msg...  │ [HAS] msg...  │ [POKI] msg... │  ← Orange tag = selected
│               │               │               │
└───────────────┴───────────────┴───────────────┘
★ SELECTED: #XQC (Press [Tab] to switch, [R] to record THIS channel)  |  Recording XQC 1:32
> 
[Tab] Select Channel  [R] Record  [S] Switch Streamers  [Ctrl+L] Clear  [Enter] Send  [Ctrl+C] Exit
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

### Getting OAuth Token

1. Visit: https://twitchtokengenerator.com/
2. Select "Bot Chat Token" or "Custom Scopes"
3. Authorize the application
4. Copy the "Access Token" (just the token, setup will add `oauth:` prefix automatically)
5. Paste during setup

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
Resize to at least 120x20 or use simple UI:
```bash
python twitch_viewer.py --channels xqc --simple-ui
```

### Multiple Streams Stopping
Reduce quality to lower bandwidth usage:
```bash
python twitch_viewer.py --channels xqc,hasan,poki --quality 720p60
```

Bandwidth requirements:
- 1 stream at best: ~6-8 Mbps
- 3 streams at best: ~18-24 Mbps
- 3 streams at 720p60: ~12-15 Mbps (more stable)

## Building Standalone Executable

### Windows

```bash
build.bat
```

Creates `dist/TwitchViewer.exe` (15-20 MB)

### Manual Build

```bash
pip install pyinstaller
pyinstaller --name=TwitchViewer --onefile --console twitch_viewer.py
```

Note: VLC and Streamlink must still be installed on target system.

## Platform Support

- **Windows**: Fully supported (Windows Terminal or PowerShell recommended)
- **macOS**: Fully supported (iTerm2 or Terminal.app)
- **Linux**: Fully supported (any modern terminal)

## Performance

- Memory: ~50-100 MB per channel
- CPU: Minimal (VLC handles decoding)
- Network: Varies by quality
- Recommended max: 3-5 channels

## Known Limitations

- Max 4 visible channel panes
- Text-only chat (Twitch emotes won't display)
- Live streams only (no VODs)
- Twitch rate limiting: 20 messages per 30 seconds

## Advanced Usage

### Shell Alias (Linux/macOS)

```bash
echo "alias twitch='python /path/to/twitch_viewer.py --channels'" >> ~/.bashrc
```

Usage:
```bash
twitch xqc,hasanabi
```

### Batch File (Windows)

Create `twitch.bat`:
```batch
@echo off
python C:\path\to\twitch_viewer.py --channels %*
```

Usage:
```batch
twitch xqc,hasanabi
```

## Logs

Application logs: `twitch_viewer.log`

View live:
```bash
tail -f twitch_viewer.log
```

## Credits

- Streamlink: https://streamlink.github.io/
- Blessed: https://github.com/jquast/blessed
- VLC Media Player: https://www.videolan.org/

## License

MIT License

## Disclaimer

This application is not affiliated with Twitch Interactive, Inc. Use at your own risk and respect Twitch's Terms of Service.
