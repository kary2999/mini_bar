"""
Meowser — 浏览器书签导入器
读取 Chrome / Edge / Brave / Arc 的 Bookmarks JSON
按文件夹分组扁平化输出
"""

import os
import json

# Chromium 系浏览器的书签文件路径（按优先级）
SOURCES = [
    ("Chrome",      "~/Library/Application Support/Google/Chrome/Default/Bookmarks"),
    ("Chrome 1",    "~/Library/Application Support/Google/Chrome/Profile 1/Bookmarks"),
    ("Chrome 2",    "~/Library/Application Support/Google/Chrome/Profile 2/Bookmarks"),
    ("Edge",        "~/Library/Application Support/Microsoft Edge/Default/Bookmarks"),
    ("Brave",       "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Bookmarks"),
    ("Arc",         "~/Library/Application Support/Arc/User Data/Default/Bookmarks"),
]


def find_sources():
    """返回所有可用书签文件: [(浏览器名, 文件路径)]"""
    out = []
    for name, p in SOURCES:
        path = os.path.expanduser(p)
        if os.path.isfile(path):
            out.append((name, path))
    return out


def load_bookmarks(path):
    """读取一个 Bookmarks 文件，返回扁平化的分组数据
    返回: {
       "groups": [
         {"name": "工作", "items": [(name, url), ...]},
         {"name": "AI 工具", "items": [(name, url), ...]},
       ],
       "total": int,
       "source": str,
    }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"groups": [], "total": 0, "error": str(e)}

    roots = data.get("roots", {})
    groups = []
    total = 0

    # 优先 bookmark_bar（书签栏）
    bar = roots.get("bookmark_bar", {})
    bar_groups, bar_total = _walk_root(bar, default_name="书签栏")
    groups.extend(bar_groups)
    total += bar_total

    # 然后 other（其他书签）
    other = roots.get("other", {})
    other_groups, other_total = _walk_root(other, default_name="其他书签")
    groups.extend(other_groups)
    total += other_total

    # synced（移动书签）
    synced = roots.get("synced", {})
    synced_groups, synced_total = _walk_root(synced, default_name="移动书签")
    if synced_total > 0:
        groups.extend(synced_groups)
        total += synced_total

    # 过滤空组
    groups = [g for g in groups if g["items"]]
    return {"groups": groups, "total": total, "source": path}


def _walk_root(node, default_name):
    """从一个 root 节点（folder）递归扁平化
    返回: ([{name, items}], total_count)
    """
    if not isinstance(node, dict):
        return [], 0

    children = node.get("children", []) or []

    # 直接散落在根下的 url 节点 → 归入 default_name 分组
    direct_urls = []
    sub_groups = []  # 子文件夹

    for ch in children:
        if not isinstance(ch, dict):
            continue
        t = ch.get("type")
        if t == "url":
            url = ch.get("url", "")
            if not _valid_url(url):
                continue
            name = (ch.get("name") or url).strip()
            direct_urls.append((name, url))
        elif t == "folder":
            # 递归把这个文件夹的所有 url 收集到一个 group 里（按文件夹名）
            folder_name = (ch.get("name") or "未命名").strip()
            urls = _collect_urls(ch)
            if urls:
                sub_groups.append({"name": folder_name, "items": urls})

    out = []
    if direct_urls:
        out.append({"name": default_name, "items": direct_urls})
    out.extend(sub_groups)

    total = sum(len(g["items"]) for g in out)
    return out, total


def _collect_urls(folder, prefix=""):
    """把一个 folder（含嵌套）拍平成 [(name, url)]
    嵌套子文件夹的内容前缀加上 "父文件夹/"
    """
    out = []
    children = folder.get("children", []) or []
    for ch in children:
        if not isinstance(ch, dict):
            continue
        t = ch.get("type")
        if t == "url":
            url = ch.get("url", "")
            if not _valid_url(url):
                continue
            name = (ch.get("name") or url).strip()
            if prefix:
                name = f"{prefix} · {name}"
            out.append((name, url))
        elif t == "folder":
            sub_name = (ch.get("name") or "").strip()
            new_prefix = f"{prefix}/{sub_name}" if prefix else sub_name
            out.extend(_collect_urls(ch, new_prefix))
    return out


def _valid_url(url):
    if not url:
        return False
    # 跳过非 http/https（chrome:// / javascript:）
    return url.startswith(("http://", "https://"))


# ─── 缓存到本地（避免每次启动都读）───
CACHE_DIR  = os.path.expanduser("~/.meowser/cache")
CACHE_PATH = os.path.join(CACHE_DIR, "bookmarks.json")


def import_first_available():
    """找第一个可用书签源，加载并缓存"""
    sources = find_sources()
    if not sources:
        return {"groups": [], "total": 0, "error": "未找到任何浏览器书签文件"}
    name, path = sources[0]
    result = load_bookmarks(path)
    result["browser"] = name
    save_cache(result)
    return result


def save_cache(data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_cache():
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ─── 生成 work 模式首页 HTML ───
WORK_HOME_PATH = os.path.join(CACHE_DIR, "home_work.html")


def _strip_credentials_and_register(url):
    """⚠ 不再写钥匙串。仅返回带凭据的原始 URL（点击后由 WebKit 自己弹输入框）"""
    return url   # 完全不动 — 让 WebKit 自然处理 401


def render_work_home(bookmarks_data):
    """根据书签数据生成 work 模式首页 HTML，写到 cache/home_work.html
    返回 file:// URL"""
    groups = bookmarks_data.get("groups", [])
    total = bookmarks_data.get("total", 0)
    source_browser = bookmarks_data.get("browser", "Chrome")

    if not groups:
        # 没有书签 → 显示引导
        html = _empty_state_html()
    else:
        html = _bookmarks_html(groups, total, source_browser)

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(WORK_HOME_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    return "file://" + WORK_HOME_PATH


def _favicon_url(url):
    """从 url 提取域名并返回 favicon URL（DuckDuckGo 服务）
    去掉 user:pass@ 和 :port 段，只保留 hostname"""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        host = (p.hostname or "").lower()
        if not host:
            return ""
        # IP 地址走 favicon 的概率很低，但不是 IP 走 ddg
        if host.replace(".", "").replace(":", "").isdigit():
            return ""    # IP 没有 favicon，让 fallback 显示
        return f"https://icons.duckduckgo.com/ip3/{host}.ico"
    except Exception:
        return ""


def _bookmarks_html(groups, total, browser_name):
    sections = []
    for g in groups:
        items_html = []
        for name, url in g["items"]:
            short = name if len(name) <= 16 else name[:14] + "…"
            # 抽 user:pass 存到钥匙串，href 用 clean URL
            clean_url = _strip_credentials_and_register(url)
            fav = _favicon_url(clean_url)
            items_html.append(
                f'<a class="card" href="{_esc(clean_url)}" title="{_esc(name)}">'
                f'<div class="card-logo"><img src="{_esc(fav)}" loading="lazy" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
                f'<div class="card-fallback">🔖</div></div>'
                f'<div class="card-name">{_esc(short)}</div>'
                f'</a>'
            )
        sections.append(
            f'<section class="group">'
            f'<div class="group-h"><span class="group-name">📂 {_esc(g["name"])}</span>'
            f'<span class="group-count">{len(g["items"])}</span></div>'
            f'<div class="grid">{"".join(items_html)}</div>'
            f'</section>'
        )

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8">
<title>Meowser — 工作模式</title>
<style>
  /* 强制白天模式 — 黑色文字 / 浅灰背景 */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
    background: #f5f5f7 !important;
    color: #1d1d1f !important;
    padding: 24px 32px 40px;
    -webkit-user-select: none;
  }}
  .header {{
    display: flex; align-items: baseline; justify-content: space-between;
    margin-bottom: 24px;
  }}
  h1 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.4px; }}
  .header-meta {{ font-size: 12px; color: #6e6e73; font-family: ui-monospace, monospace; }}
  .group {{ margin-bottom: 28px; }}
  .group-h {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 4px 10px;
    font-size: 12px; font-weight: 600;
    color: #6e6e73;
    text-transform: uppercase; letter-spacing: 0.5px;
  }}
  .group-name {{ display: flex; align-items: center; gap: 8px; }}
  .group-count {{
    padding: 1px 8px; border-radius: 999px;
    background: rgba(0,0,0,0.05); color: #6e6e73;
    font-size: 10px; font-weight: 600;
    font-family: ui-monospace, monospace;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 8px;
  }}
  .card {{
    background: white;
    border: 0.5px solid rgba(0,0,0,0.08);
    border-radius: 10px;
    padding: 12px 6px;
    text-align: center;
    text-decoration: none; color: inherit;
    transition: all 0.18s cubic-bezier(0.16,1,0.3,1);
    cursor: pointer;
    display: flex; flex-direction: column; align-items: center; gap: 6px;
  }}
  .card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(0,0,0,0.06);
  }}
  .card-logo {{
    width: 32px; height: 32px;
    border-radius: 7px;
    background: rgba(0,0,0,0.04);
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
    position: relative;
  }}
  .card-logo img {{ width: 22px; height: 22px; object-fit: contain; }}
  .card-fallback {{
    display: none; position: absolute;
    inset: 0; align-items: center; justify-content: center;
    font-size: 16px;
  }}
  .card-name {{
    font-size: 11px; font-weight: 500;
    color: #1d1d1f !important;   /* 永远黑色 — 禁止白色 */
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    max-width: 100%;
  }}
  .group-h {{ color: #424245 !important; }}
  .group-count {{ background: rgba(0,0,0,0.05) !important; color: #6e6e73 !important; }}
  .header-meta {{ color: #6e6e73 !important; }}
  h1 {{ color: #1d1d1f !important; }}
</style>
</head>
<body>
  <div class="header">
    <h1>📑 我的书签</h1>
    <div class="header-meta">从 {_esc(browser_name)} 导入 · {total} 个 · {len(groups)} 组</div>
  </div>
  {"".join(sections)}
</body></html>
'''


def _empty_state_html():
    return '''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><title>Meowser — 工作模式</title>
<style>
  body {
    font-family: -apple-system, "PingFang SC", sans-serif;
    background: #f5f5f7; color: #1d1d1f;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; margin: 0; padding: 40px;
    text-align: center;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #1c1c1e; color: #f5f5f7; }
  }
  .card {
    background: white; border-radius: 16px;
    padding: 40px 48px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.08);
    max-width: 480px;
  }
  @media (prefers-color-scheme: dark) {
    .card { background: rgba(255,255,255,0.06); }
  }
  .ico { font-size: 56px; margin-bottom: 14px; }
  h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; margin-bottom: 6px; }
  p { font-size: 13px; line-height: 1.6; color: #6e6e73; }
  .kbd {
    display: inline-block; padding: 1px 8px;
    background: rgba(0,0,0,0.06); border-radius: 5px;
    font-family: ui-monospace, monospace; font-size: 12px;
    margin: 0 2px;
  }
</style>
</head><body>
<div class="card">
  <div class="ico">📑</div>
  <h1>工作模式 · 书签为空</h1>
  <p>没找到 Chrome / Edge / Brave / Arc 的书签文件。<br><br>
  请打开 Chrome 同步书签，或在菜单栏 <span class="kbd">🐱</span> →
  <span class="kbd">📥 导入书签</span> 手动指定文件。</p>
</div>
</body></html>
'''


def _esc(s):
    """简易 HTML 转义"""
    if not isinstance(s, str):
        s = str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))
