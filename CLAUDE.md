# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Meowser** is a floating browser for macOS—a menubar app that provides lightweight web content viewing in resizable windows alongside your work. It supports multiple user profiles with separate proxy settings, window layouts, and bookmarks.

## Build & Development

### Setup
```bash
# Install dependencies
pip install -r requirements.txt
```

### Run (Development)
```bash
# Launch directly with Python
python3 main.py
```

The app will start with the launcher window to select a profile, then create a Boss + main window.

### Build for macOS
```bash
# One-step build and package
./build.sh
```

Outputs:
- `dist/Meowser.app` — binary for testing
- `dist/Meowser-vX.Y.Z.zip` — distribution package (app + launch script + instructions)

The build script handles dependency checks, py2app compilation, ad-hoc signing, and zip creation.

### Tests
```bash
python3 test_self.py              # Core module tests
python3 test_meowser_load.py      # Full app launch test
python3 test_webview_standalone.py # WebView-only test
```

### Version
Edit the `CFBundleShortVersionString` in `setup.py` to update the version. `build.sh` reads this automatically.

## Architecture

### Core Abstraction: Boss / Child Windows

The app uses a **Boss/Child window hierarchy** to manage multiple floating windows:

- **Boss**: Represents a user-selected Profile (e.g., "Work", "Personal"). One Boss per profile session.
- **Children**: All other windows created while that Boss is active. They share the Boss's webdata directory, proxy settings, and layout manager.
- **LayoutManager**: Automatically arranges children in a grid/cascade pattern on screen edges.

```
App (NSApplication)
 ├─ Boss "Work"
 │  ├─ Main window (1200×800, address bar)
 │  ├─ Child 1 (200×150, floating)
 │  ├─ Child 2 (200×150, floating)
 │  └─ LayoutManager (handles tiling/cascade)
 │
 └─ Boss "Personal" (switched via launcher)
    ├─ Main window
    └─ Children...
```

When the user switches profiles via the launcher, the old Boss's windows close and a new Boss is created.

### File Structure

| File | Role |
|------|------|
| `main.py` | App entry point; `AppDelegate` manages Boss lifecycle, hotkeys, menu |
| `browser.py` | `StealthWindow` — WKWebView with small/big mode switching, address bar |
| `boss_manager.py` | `Boss` class + global registry; tracks profile state |
| `layout_manager.py` | `LayoutManager` — auto-arranges windows on screen edges (tile/cascade) |
| `menu.py` | Status bar icon + `NSPopover` menu (window controls, settings, presets) |
| `launcher.py` | Profile picker window (shown at startup or when switching profiles) |
| `config.py` | `~/.meowser/config.json` — hotkeys, layouts, profiles, proxy config |
| `hotkey.py` | Global hotkey registration (Carbon APIs) |
| `proxy.py` | Proxy configuration and WebKit integration |
| `profiles.py` | Profile definitions and management |
| `edit_window.py` | Address bar and URL editor windows |
| `bookmarks.py` | Bookmark parsing and menu building |
| `onepass.py` | 1Password integration |

### Key Classes & Lifecycle

1. **AppDelegate** (`main.py`): 
   - Registers global hotkeys on launch
   - Creates/destroys Boss instances when user switches profiles
   - Manages the status bar menu

2. **Boss** (`boss_manager.py`):
   - Owns a `LayoutManager` for its children
   - Holds profile name and config (proxy, mode, etc.)
   - `close_all()` destroys all windows when switching profiles

3. **StealthWindow** (`browser.py`):
   - macOS `NSWindow` with embedded WKWebView
   - Toggles between small (200×150) and big (1200×800) modes
   - Small mode scales the page via `CATransform3DMakeScale`; big mode shows a full address bar

4. **LayoutManager** (`layout_manager.py`):
   - Maintains an ordered list of windows
   - Auto-arranges them based on edge (left/right/top/bottom) and style (tile/cascade)
   - Recalculates on window close or config change

### Window Modes

- **Small window (200×150)**: Floating, positioned by LayoutManager, entire page scaled down.
- **Big window (1200×800)**: Full-featured with address bar (36px), transparency slider, navigation.
- **Transition**: Double-click in small mode → expand; click outside in big mode → shrink.

### Configuration

User config at `~/.meowser/config.json`:

```json
{
  "toggle_hotkey": {"modifiers": ["alt"], "key": "~"},
  "default_url": "https://www.youtube.com",
  "small_window_size": {"w": 200, "h": 150},
  "layout": {
    "edge": "left",
    "style": "tile",
    "gap": 8,
    "auto_reflow": true
  },
  "profile": {
    "name": "默认",
    "mode": "work",
    "proxy": {"type": "direct"}
  }
}
```

Hotkey format: `{"modifiers": ["cmd", "alt", ...], "key": "Q"}` (key is single char or symbol).

## Platform & Dependencies

- **Python 3.8+**
- **macOS 11+** (Big Sur, Monterey, Ventura, Sonoma)
- **Apple Silicon** (M1/M2/M3/M4/M5) native; Intel builds possible but untested
- **PyObjC 9.0+**: Bridges Python to Cocoa (AppKit, WebKit, Quartz)
- **py2app 0.28+**: Packages Python app as `.app` bundle

The app uses `LSUIElement: true` to hide from Dock and appear only in the menubar.

## Common Tasks

### Add a new hotkey
1. Define it in `config.py` under `DEFAULT_CONFIG`
2. Register in `AppDelegate._apply_hotkeys()` via `get_manager().register_hotkey()`
3. Handle the callback method

### Add a menu item
Edit `menu.py` → `StatusBarController.build_menu()`.

### Customize window layout
Adjust `layout_manager.py` edge/style/gap logic or expose new layout options in the menu.

### Add a new proxy type
Edit `proxy.py` to handle the new type and integrate with `WKWebView` configuration.

## Testing Notes

- Tests use Python's `unittest` framework; no external test runner configured.
- `test_self.py` imports core modules to check for syntax/import errors.
- `test_meowser_load.py` attempts a full app launch (requires macOS + X11/display).
- Tests assume PyObjC and WebKit are installed; headless CI may need special setup.
