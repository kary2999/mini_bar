"""
Meowser — 工作区（Profile）CRUD
~/.meowser/profiles.json 保存工作区列表，与 config.json 分离
"""

import json
import os
import uuid

PROFILES_DIR = os.path.expanduser("~/.meowser")
PROFILES_PATH = os.path.join(PROFILES_DIR, "profiles.json")


DEFAULT_PROFILES = [
    {
        "id":    "p_default",
        "name":  "默认",
        "note":  "本地直连 · 默认工作区",
        "emoji": "🐱",
        "color": "fun",          # fun / work / crypto / news
        "mode":  "work",         # work / slack
        "theme": "yellow",       # red / green / yellow — 浏览器边框/地址栏配色
        "proxy": {"type": "direct"},
        "show_bookmarks": False,
    },
    {
        "id":    "p_work",
        "name":  "工作",
        "note":  "公司 V2Ray · 走 SOCKS5",
        "emoji": "💻",
        "color": "work",
        "mode":  "work",
        "theme": "green",
        "proxy": {"type": "socks5", "host": "127.0.0.1", "port": 1087},
        "show_bookmarks": True,
    },
    {
        "id":    "p_fun",
        "name":  "娱乐",
        "note":  "摸鱼 · 直连不卡顿",
        "emoji": "🎮",
        "color": "fun",
        "mode":  "slack",
        "theme": "red",
        "proxy": {"type": "direct"},
        "show_bookmarks": False,
    },
]


def load_profiles():
    if not os.path.exists(PROFILES_PATH):
        save_profiles(DEFAULT_PROFILES)
        return list(DEFAULT_PROFILES)
    try:
        with open(PROFILES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            return list(DEFAULT_PROFILES)
        return data
    except Exception:
        return list(DEFAULT_PROFILES)


def save_profiles(profiles):
    os.makedirs(PROFILES_DIR, exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def make_blank():
    """新建空白 profile"""
    return {
        "id":    f"p_{uuid.uuid4().hex[:8]}",
        "name":  "新工作区",
        "note":  "",
        "emoji": "✨",
        "color": "fun",
        "mode":  "work",
        "theme": "yellow",
        "proxy": {"type": "direct"},
        "show_bookmarks": False,
    }


def find_by_id(profiles, pid):
    for p in profiles:
        if p.get("id") == pid:
            return p
    return None


def upsert(profiles, profile):
    """新增/更新一个 profile，返回新列表"""
    pid = profile.get("id")
    out = []
    found = False
    for p in profiles:
        if p.get("id") == pid:
            out.append(profile); found = True
        else:
            out.append(p)
    if not found:
        out.append(profile)
    return out


def delete(profiles, pid):
    return [p for p in profiles if p.get("id") != pid]
