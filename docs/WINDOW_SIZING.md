# Window Sizing Guide for nTwitch

## How Window Sizing Works

nTwitch uses Textual, a terminal UI framework that automatically adapts to your terminal window size. The application **cannot set** the window size itself - instead, it responds to whatever size your terminal window is.

## How to Control Window Size

### Windows Terminal (Recommended)
1. Open Windows Terminal settings (Ctrl+,)
2. Go to your profile settings
3. Under "Appearance" > "Initial size"
   - Set **Columns**: 150-200 (width)
   - Set **Rows**: 40-50 (height)

### Command Prompt
1. Right-click title bar → Properties
2. Go to "Layout" tab
3. Set:
   - **Screen Buffer Width**: 150-200
   - **Screen Buffer Height**: 500-9999 (for scrollback)
   - **Window Width**: 150-200
   - **Window Height**: 40-50

### PowerShell
1. Right-click title bar → Properties
2. Same as Command Prompt above

### Windows Terminal with Launch Parameters
```powershell
wt.exe -w 0 --size 160,50
```
- `-w 0`: Use first window
- `--size 160,50`: Set to 160 columns × 50 rows

## Recommended Sizes

### For 1-2 Channels
- **Width**: 120-150 columns
- **Height**: 35-45 rows

### For 3-4 Channels
- **Width**: 180-200 columns
- **Height**: 40-50 rows

### For 5 Channels (Maximum)
- **Width**: 220+ columns
- **Height**: 45-50 rows

## Application UI Elements

### Channel Selection Screen
- **Fixed width**: 90 characters
- **Height**: Auto-adjusts to content
- Centered in terminal

### Main Viewer UI
- **Adapts to full terminal size**
- Channels split horizontally
- Each channel gets equal width
- Chat input at bottom (3 rows)
- Status bar (1 row)
- Footer with key bindings (1 row)

## Tips

1. **Fullscreen Mode**: Press F11 in most terminals
2. **Font Size**: Smaller fonts = more content (Ctrl+Mouse Wheel)
3. **Testing**: Resize your terminal while the app is running - it adapts in real-time!
4. **Multiple Monitors**: Drag terminal to larger monitor for more space

## Example: Launch with Specific Size

### Create a Batch File
```batch
@echo off
REM Launch nTwitch with optimal window size
wt.exe --size 180,45 python nTwitch.py
```

### Create a PowerShell Script
```powershell
# Set console size then launch
$host.UI.RawUI.WindowSize = New-Object System.Management.Automation.Host.Size(180, 45)
python nTwitch.py
```

## Code Location for UI Sizing

If you want to modify the UI sizing in the code:

### Channel Selection Dialog
**File**: `src/terminal_ui.py`
**Class**: `ChannelSelectionApp`
**Line**: ~690
```python
#selection-container {
    width: 90;  # Change this for wider/narrower dialog
    height: auto;
    ...
}
```

### Main Chat Window
The main chat UI automatically fills the terminal. To change channel pane behavior:
**File**: `src/terminal_ui.py`
**Class**: `ChannelPane`
**Line**: ~35-75 (CSS section)

Chat panes split the terminal width equally. This is controlled by:
```css
width: 1fr;  # Each pane gets 1 "fraction" of available space
```

## Troubleshooting

### Text is cut off
- **Solution**: Increase terminal width

### Channels are cramped
- **Solution**: Use fewer channels or increase terminal width

### Can't see full messages
- **Solution**: Increase terminal width or use fewer channels

### UI looks wrong
- **Solution**: Terminal too small - minimum 80x24, recommended 150x40+
