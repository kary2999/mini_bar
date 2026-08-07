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

1. **Launch**: Click the menu bar icon (●)
2. **Choose Profile**: Select a workspace (Work, Personal, etc.)
3. **Create Windows**: New floating windows appear at screen edges
4. **Control**:
   - `⌘⌥B` — Show/hide all windows (global hotkey)
   - `⌘⌥R` — Rearrange layout
   - `⌘⌥Q` — Quit
   - Double-click small window → expand to full view
   - Click outside full view → shrink back

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

## Configuration

User settings are stored in `~/.meowser/config.json`:

```json
{
  "toggle_hotkey": {"modifiers": ["alt"], "key": "~"},
  "default_url": "https://www.youtube.com",
  "layout": {
    "edge": "left",
    "style": "tile",
    "gap": 8
  }
}
```

Edit directly or use the Settings panel in the menu.

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
