"""
Meowser 自测：覆盖所有模块的关键路径
跑法: python3 test_self.py
"""

import os, sys, json, tempfile, shutil

def section(name):
    print()
    print("=" * 60)
    print(f"  {name}")
    print("=" * 60)

ok_count = 0
fail_count = 0
warns = []

def check(label, cond, detail=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  ✓ {label}")
        if detail:
            print(f"      {detail}")
    else:
        fail_count += 1
        print(f"  ✗ {label}")
        if detail:
            print(f"      {detail}")

def warn(msg):
    warns.append(msg)
    print(f"  ⚠ {msg}")


# ──────── 1. 模块导入 ────────
section("1. 模块导入")
mods = ["config", "layout_manager", "boss_manager", "proxy",
        "profiles", "edit_window", "launcher", "bookmarks",
        "browser", "menu", "main"]
for m in mods:
    try:
        __import__(m)
        check(f"import {m}", True)
    except Exception as e:
        check(f"import {m}", False, str(e))


# ──────── 2. config ────────
section("2. config 加载/合并")
import config
cfg = config.load_config()
check("load_config 返回 dict", isinstance(cfg, dict))
check("有 toggle_hotkey", "toggle_hotkey" in cfg)
check("有 quit_hotkey", "quit_hotkey" in cfg)
check("有 rearrange_hotkey", "rearrange_hotkey" in cfg)
check("有 layout 字段", isinstance(cfg.get("layout"), dict))
check("有 small_window_size", isinstance(cfg.get("small_window_size"), dict))
check("有 profile", isinstance(cfg.get("profile"), dict))

mods, code = config.hotkey_to_carbon({"modifiers": ["cmd", "alt"], "key": "B"})
check("hotkey_to_carbon ⌘⌥B", code == 11 and (mods & (1 << 8)) and (mods & (1 << 11)),
      f"mods=0x{mods:x} code={code}")
check("hotkey_to_carbon ⌥~", config.hotkey_to_carbon({"modifiers": ["alt"], "key": "~"})[1] == 50)

check("SMALL_SIZE_PRESETS 至少 9 档", len(config.SMALL_SIZE_PRESETS) >= 9,
      f"实际 {len(config.SMALL_SIZE_PRESETS)} 档")
check("含 60×45", any(w == 60 and h == 45 for _, w, h in config.SMALL_SIZE_PRESETS))
check("含 800×600", any(w == 800 and h == 600 for _, w, h in config.SMALL_SIZE_PRESETS))


# ──────── 3. profiles ────────
section("3. profiles CRUD")
import profiles
ps = profiles.load_profiles()
check("默认至少 3 个 profile", len(ps) >= 3, f"实际 {len(ps)} 个")
check("默认 profile 有 id/name/mode/proxy",
      all(("id" in p and "name" in p and "mode" in p and "proxy" in p) for p in ps))

blank = profiles.make_blank()
check("make_blank 返回完整字段",
      all(k in blank for k in ("id", "name", "emoji", "color", "mode", "proxy")))
check("make_blank id 唯一", blank["id"] not in [p["id"] for p in ps])

# upsert + delete dry run
fake = dict(blank); fake["name"] = "TEST_TMP"
ps2 = profiles.upsert(ps, fake)
check("upsert 添加新 profile", len(ps2) == len(ps) + 1)
ps3 = profiles.delete(ps2, fake["id"])
check("delete 删除", len(ps3) == len(ps))


# ──────── 4. layout_manager ────────
section("4. layout_manager")
from layout_manager import LayoutManager
lm = LayoutManager()
check("默认 edge=left", lm.get_state()["edge"] == "left")
check("默认 style=tile", lm.get_state()["style"] == "tile")
lm.set_edge("right")
lm.set_style("cascade")
lm.set_gap(20)
st = lm.get_state()
check("set_edge right", st["edge"] == "right")
check("set_style cascade", st["style"] == "cascade")
check("set_gap 20", st["gap"] == 20)

# 校验非法值不修改
lm.set_edge("nonsense")
check("非法 edge 不修改", lm.get_state()["edge"] == "right")


# ──────── 5. boss_manager ────────
section("5. boss_manager")
from boss_manager import create_boss, get_active_boss, all_bosses, find_boss_for_window
b = create_boss(profile_name="TEST_BOSS", profile_cfg={"name": "TEST_BOSS"})
check("create_boss 返回非空", b is not None)
check("get_active_boss == 新建的", get_active_boss() is b)
check("all_bosses 包含它", b in all_bosses())
check("Boss 默认 main_window 为 None", b.main_window() is None)
check("Boss 子窗口列表为空", b._child_windows == [])


# ──────── 6. proxy ────────
section("6. proxy")
import proxy
check("Network framework 可用", proxy.is_available(),
      "如果失败，macOS 14 以下没法做每窗口代理")
# 构造测试
cfg_obj = proxy.make_proxy_config("socks5", "127.0.0.1", 1087)
if cfg_obj is not None:
    check("make_proxy_config socks5 成功", True)
else:
    warn("make_proxy_config 返回 None — 可能是 macOS 13 以下")


# ──────── 7. bookmarks ────────
section("7. bookmarks 导入")
import bookmarks
sources = bookmarks.find_sources()
check("能找到至少 1 个浏览器书签", len(sources) >= 1,
      f"找到: {[s[0] for s in sources]}")

if sources:
    name, path = sources[0]
    data = bookmarks.load_bookmarks(path)
    n = data.get("total", 0)
    g = len(data.get("groups", []))
    check("书签解析非空", n > 0, f"{name}: {n} 个 / {g} 组")
    # 验证扁平化产出
    if g > 0:
        first_g = data["groups"][0]
        check("分组有 name + items", "name" in first_g and "items" in first_g)
        if first_g["items"]:
            first_item = first_g["items"][0]
            check("item 是 (name, url) 二元组", isinstance(first_item, tuple) and len(first_item) == 2)
            url = first_item[1]
            check("url 是 http/https", url.startswith(("http://", "https://")))

    # 渲染 home_work.html
    out_url = bookmarks.render_work_home(data)
    check("生成 home_work.html", out_url.startswith("file://"))
    # 检查文件能读
    fp = out_url[len("file://"):]
    check("home_work.html 可读", os.path.isfile(fp) and os.path.getsize(fp) > 1000)
    # 验证 HTML 语法基本完整
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    check("HTML 含 <a class=\"card\"", '<a class="card"' in html)
    check("HTML 含分组 group-h", "group-h" in html)
    check("HTML 不含未转义 & (除 &amp;/&lt;/&gt;/&quot;/&#39;)",
          not any(s in html for s in [" & ", " &x"]))

    # 验证 _favicon_url 处理 user:pass@
    fav = bookmarks._favicon_url("http://user:pass@1.2.3.4:1234/x")
    check("favicon 不带 user:pass", "user:pass" not in fav and "@" not in fav)
    check("IP 地址 favicon 返回空", bookmarks._favicon_url("http://1.2.3.4:80/") == "")


# ──────── 8. cache 状态 ────────
section("8. cache / 配置目录")
config_dir = os.path.expanduser("~/.meowser")
check("~/.meowser 存在", os.path.isdir(config_dir))
cache_dir = os.path.expanduser("~/.meowser/cache")
check("~/.meowser/cache 存在", os.path.isdir(cache_dir))
prof_path = os.path.join(config_dir, "profiles.json")
check("profiles.json 存在", os.path.isfile(prof_path))


# ──────── 9. 关键 ObjC 选择器存在性 ────────
section("9. ObjC 方法签名")
import browser, menu, edit_window, launcher

def has_method(klass, name):
    return hasattr(klass, name)

check("StealthWindow.toggleZoom", has_method(browser.StealthWindow, "toggleZoom"))
check("StealthWindow.setSmallSizeW_h_", has_method(browser.StealthWindow, "setSmallSizeW_h_"))
check("StealthWindow.goHome", has_method(browser.StealthWindow, "goHome"))
check("StealthWindow.doNewWindow_", has_method(browser.StealthWindow, "doNewWindow_"))
check("StealthWindow.doRearrange_", has_method(browser.StealthWindow, "doRearrange_"))
check("StealthWindow.doTogglePin_", has_method(browser.StealthWindow, "doTogglePin_"))
check("NavDelegate 类存在", hasattr(browser, "NavDelegate"))
check("NavDelegate 不实现 decidePolicy（避免 PyObjC block 踩坑）",
      not has_method(browser.NavDelegate, "webView_decidePolicyForNavigationAction_decisionHandler_"))
check("NavDelegate 有 didReceiveAuthenticationChallenge",
      has_method(browser.NavDelegate, "webView_didReceiveAuthenticationChallenge_completionHandler_"))

check("StatusBarController.togglePopover_", has_method(menu.StatusBarController, "togglePopover_"))
check("StatusBarController.openLauncher_", has_method(menu.StatusBarController, "openLauncher_"))
check("StatusBarController.importBookmarks_", has_method(menu.StatusBarController, "importBookmarks_"))
check("StatusBarController.editProxy_", has_method(menu.StatusBarController, "editProxy_"))
check("StatusBarController.editCustomSize_", has_method(menu.StatusBarController, "editCustomSize_"))
check("StatusBarController.openInSafari_", has_method(menu.StatusBarController, "openInSafari_"))

check("LauncherController.show", has_method(launcher.LauncherController, "show"))
check("LauncherController.launchProfile_", has_method(launcher.LauncherController, "launchProfile_"))
check("LauncherController.editProfile_", has_method(launcher.LauncherController, "editProfile_"))
check("LauncherController.syncCookies_", has_method(launcher.LauncherController, "syncCookies_"))

check("EditWindowController.show", has_method(edit_window.EditWindowController, "show"))
check("EditWindowController.doSave_", has_method(edit_window.EditWindowController, "doSave_"))
check("EditWindowController.doDelete_", has_method(edit_window.EditWindowController, "doDelete_"))
check("EditWindowController.pickProxyType_", has_method(edit_window.EditWindowController, "pickProxyType_"))


# ──────── 总结 ────────
print()
print("=" * 60)
print(f"  结果: {ok_count} 通过, {fail_count} 失败, {len(warns)} 警告")
print("=" * 60)
if warns:
    print("\n警告：")
    for w in warns:
        print(f"  ⚠ {w}")
sys.exit(0 if fail_count == 0 else 1)
