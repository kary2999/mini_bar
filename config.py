"""
Meowser — 配置文件读写
~/.meowser/config.json 保存快捷键等用户偏好
"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.meowser")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "toggle_hotkey":      {"modifiers": ["alt"], "key": "~"},
    "quit_hotkey":        {"modifiers": ["cmd", "alt"], "key": "Q"},
    "rearrange_hotkey":   {"modifiers": ["cmd", "alt"], "key": "R"},
    "default_url":        "https://www.youtube.com",
    "small_window_size":  {"w": 200, "h": 150},

    # 摆放配置
    "layout": {
        "edge":    "left",     # left / right / top / bottom
        "style":   "tile",     # tile / cascade
        "gap":     8,          # 像素间距
        "auto_reflow": True    # 关闭后自动补位
    },

    # Profile / Boss 配置
    "profile": {
        "name":  "默认",
        "mode":  "work",       # work / slack
        "proxy": {"type": "direct"},   # direct / system / http / socks5
    },
}

# 小窗尺寸预设（9 档，覆盖极小到半屏）
SMALL_SIZE_PRESETS = [
    ("极小 60×45",      60,   45),
    ("迷你 120×90",    120,   90),
    ("小 150×110",     150,  110),
    ("中 200×150",     200,  150),
    ("大 260×195",     260,  195),
    ("更大 320×240",   320,  240),
    ("展开 400×300",   400,  300),
    ("半屏 500×375",   500,  375),
    ("大半屏 640×480", 640,  480),
    ("巨幅 800×600",   800,  600),
]


def _deep_merge(base, override):
    """嵌套 dict 深合并"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config():
    import copy
    if not os.path.exists(CONFIG_PATH):
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return _deep_merge(DEFAULT_CONFIG, cfg)
    except Exception:
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# 修饰键名 → Carbon 掩码
CARBON_MODIFIER_MAP = {
    "cmd":   1 << 8,    # cmdKey
    "shift": 1 << 9,
    "alt":   1 << 11,   # optionKey
    "opt":   1 << 11,
    "ctrl":  1 << 12,
}

# 常见按键名 → Carbon virtual keycode
KEYCODE_MAP = {
    "A": 0, "S": 1, "D": 2, "F": 3, "H": 4, "G": 5, "Z": 6, "X": 7,
    "C": 8, "V": 9, "B": 11, "Q": 12, "W": 13, "E": 14, "R": 15,
    "Y": 16, "T": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "O": 31, "U": 32, "[": 33, "I": 34, "P": 35,
    "L": 37, "J": 38, "'": 39, "K": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "N": 45, "M": 46, ".": 47,
    "SPACE": 49, "TAB": 48, "ESC": 53,
    "`": 50, "~": 50,  # grave/tilde 同一物理键
    "F1": 122, "F2": 120, "F3": 99, "F4": 118, "F5": 96,
    "F6": 97, "F7": 98, "F8": 100, "F9": 101, "F10": 109,
    "F11": 103, "F12": 111,
}


def hotkey_to_carbon(hk):
    """把 config 里的 hotkey dict 转为 (modifier_mask, keycode) """
    mods = 0
    for m in hk.get("modifiers", []):
        mods |= CARBON_MODIFIER_MAP.get(m.lower(), 0)
    key = hk.get("key", "").upper()
    code = KEYCODE_MAP.get(key, -1)
    return mods, code


def hotkey_display(hk):
    """生成人类可读的快捷键字符串，如 ⌘⌥B"""
    symbol_map = {"cmd": "⌘", "shift": "⇧", "alt": "⌥", "opt": "⌥", "ctrl": "⌃"}
    mods = "".join(symbol_map.get(m.lower(), m) for m in hk.get("modifiers", []))
    return mods + hk.get("key", "").upper()
