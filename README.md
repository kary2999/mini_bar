# Meowser — Floating Browser for macOS

A lightweight, always-on-top browser for macOS. Perfect for keeping reference material, documentation, or communication tools visible while you work.

## Features

🖼️ **Floating Windows** — Multiple independent browser windows that stay on top  
🎨 **Small/Big Modes** — Toggle between compact (200×150) and full-featured (1200×800) views  
⌨️ **Global Hotkeys** — Show/hide, create windows, rearrange layout with keyboard shortcuts  
📋 **Profiles** — Switch between separate workspace configurations (proxy, bookmarks, etc.)  
🔀 **Auto-Layout** — Windows automatically arrange in tile or cascade patterns  
🌐 **Proxy Support** — Direct, system, HTTP, or SOCKS5 proxy configuration  
📌 **Menubar App** — Minimal footprint, fully controllable from the status bar

## Installation

### From Release
1. Download the latest `Meowser-vX.Y.Z.zip` from [Releases](https://github.com/kary2999/mini_bar/releases)
2. Extract and double-click `打开.command` (Open)
3. The app appears as a small dot (●) in the menu bar

### From Source
```bash
git clone https://github.com/kary2999/mini_bar.git
cd mini_bar

# Build and package
./build.sh

# Run the built app
open dist/Meowser.app
```

## Quick Start

### First Launch
1. **Extract & Open**: Double-click `打开.command` from the zip
2. **Grant Permission**: Click "Open" when macOS shows security warning
3. **Select Profile**: Choose a workspace (Work, Personal, etc.) from launcher
4. **Done**: Small browser window appears at screen edge

### Daily Usage

```
┌─────────────────────────────────────────────┐
│ Menu Bar                         [●] Meowser │  ← Click here to control
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ⌘⌥B: Show/Hide                              │
│ ⌘⌥R: Rearrange windows                      │
│ ⌘⌥Q: Quit                                   │
│                                              │
│ [New Window]  [Layout ⋮]  [Settings] [Exit] │  ← Popover menu
└─────────────────────────────────────────────┘
```

### Window Modes

**Small Window (200×150)** — Compact floating view
```
┌──────────────┐
│              │
│ Scaled down  │  Double-click to expand
│ web content  │
│              │
└──────────────┘
```

**Big Window (1200×800)** — Full-featured view
```
┌────────────────────────────────────────────────────┐
│ ◀  ▶  ⟲  https://example.com              ◐─────⊕  │  Address bar + controls
├────────────────────────────────────────────────────┤
│                                                    │
│                   Web Content                      │
│                   (full size)                      │
│                                                    │
└────────────────────────────────────────────────────┘
```

Click outside big window → auto-shrinks to small

### Hotkey Reference

| Hotkey | Action |
|--------|--------|
| `⌘⌥B` | Show/hide all floating windows (global, works anytime) |
| `⌘⌥R` | Rearrange windows (tile/cascade based on layout setting) |
| `⌘⌥Q` | Quit Meowser |
| Double-click small window | Expand to big view |
| Click outside big window | Collapse to small view |

### Menu Features

Click the **●** menu bar icon to access:

- **Profile Status** — Shows current workspace name & window count
- **New Window** — Create another floating browser window
- **Quick Actions** — Show/hide, rearrange, go home
- **Window Size** — Choose from 10 preset sizes (60×45 ~ 800×600)
- **Layout** — Switch between "Tile" and "Cascade" arrangement
  - **Edge**: Left/Right/Top/Bottom
  - **Spacing**: Adjust gap between windows
- **Quick Links** — Bookmarks from your browser (Chrome, Safari, etc.)
- **Address Bar** — Type or paste URL directly
- **Proxy Settings** — Configure per-profile proxy (direct/system/HTTP/SOCKS5)
- **Settings** — Edit hotkeys, default URL, layout behavior
- **Pin Window** — Keep a window on top always (useful during presentations)

## System Requirements

- **macOS 11** (Big Sur) or later
- **Apple Silicon** (M1/M2/M3/M4/M5)
- **Python 3.8+** (for development only)

## Development

See [CLAUDE.md](CLAUDE.md) for detailed build instructions, architecture, and development guide.

### Quick Commands
```bash
# Setup
pip install -r requirements.txt

# Run development
python3 main.py

# Test
python3 test_self.py

# Build for distribution
./build.sh
```

## Use Cases

### 📺 Watch While Working
Keep YouTube, Twitch, or video content visible while coding
```
[Main Editor]                    [Small Browser]
                                 [  YouTube  ]
                                 [ 200×150   ]
```

### 📋 Reference Material
Docstrings, APIs, documentation always accessible
```
[IDE]                            [Browser]
[Code Editor]          or        [Docs]
                                 [MDN/StackOverflow]
```

### 💬 Always-On Communication
Keep Slack, Discord, or mail preview visible (tile multiple windows)
```
[Main Work Area]  [Slack] [Email] [Chat]
                  [150×150]
```

### 🎯 Multi-Profile Workflow
Switch between contexts instantly:
- **Work**: VPN proxy, corporate bookmarks, gmail.com
- **Personal**: Direct internet, personal bookmarks
- **Research**: Specific bookmarks & layout setup

Switch via menu → All windows refresh with new profile settings

## Configuration

User settings are stored in `~/.meowser/config.json`:

```json
{
  "toggle_hotkey": {"modifiers": ["cmd", "alt"], "key": "B"},
  "quit_hotkey": {"modifiers": ["cmd", "alt"], "key": "Q"},
  "rearrange_hotkey": {"modifiers": ["cmd", "alt"], "key": "R"},
  "default_url": "https://www.youtube.com",
  "small_window_size": {"w": 200, "h": 150},
  "layout": {
    "edge": "left",
    "style": "tile",
    "gap": 8,
    "auto_reflow": true
  },
  "profile": {
    "name": "Work",
    "mode": "work",
    "proxy": {"type": "direct"}
  }
}
```

Edit directly or use the **Settings** panel in the menu.

### Proxy Configuration

Each profile can have independent proxy settings:

```json
{
  "type": "direct"           // No proxy
}

{
  "type": "system"           // Use system proxy
}

{
  "type": "http",
  "host": "proxy.corp.com",
  "port": 8080,
  "username": "user",
  "password": "pass"
}

{
  "type": "socks5",
  "host": "localhost",
  "port": 1080
}
```

## Troubleshooting

### "Meowser is damaged and can't be opened"
This is a Gatekeeper warning for unsigned apps. Solution:
```bash
xattr -cr /Applications/Meowser.app
```
Or double-click `打开.command` from the zip (it does this automatically).

### Windows not appearing
- Check menu bar for ● icon (may be hidden by other apps)
- Try hotkey `⌘⌥B` to show windows
- Restart app if needed: Quit via menu → `⌘⌥Q`

### Proxy not working
- Verify proxy settings in menu → Proxy Settings
- Test connectivity: Try loading a simple URL first
- Check if proxy requires authentication (add username/password in config)

### App crashes
- Check logs: `~/Library/Logs/Meowser.log` (if available)
- Try resetting config: `rm ~/.meowser/config.json`
- Report issue with error message on [GitHub Issues](https://github.com/kary2999/mini_bar/issues)

## Architecture

Meowser uses a **Boss/Child window system**:
- **Boss**: Represents a profile (Work, Personal, etc.)
- **Children**: Individual floating windows managed by the Boss
- **LayoutManager**: Automatically arranges windows in tile or cascade patterns

See [CLAUDE.md](CLAUDE.md) for full architecture details.

## License

See LICENSE file (if applicable).

## Support

For issues, features, or questions, open an [issue on GitHub](https://github.com/kary2999/mini_bar/issues).
