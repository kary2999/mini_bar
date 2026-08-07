"""
完全用 Meowser 的代码路径（含代理 + NavDelegate）加载 Google 翻译
验证 Meowser 的实际加载是否成功
"""
import sys, time, json, os
from AppKit import (
    NSApplication, NSWindow, NSMakeRect, NSBackingStoreBuffered,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
)
from WebKit import WKWebView, WKWebViewConfiguration, WKWebsiteDataStore
from Foundation import NSURL, NSURLRequest, NSRunLoop, NSDate, NSLog


def main():
    app = NSApplication.sharedApplication()

    # 读 Meowser 配置
    cfg_path = os.path.expanduser("~/.meowser/config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
    proxy_dict = (cfg.get("profile", {}) or {}).get("proxy", {"type": "direct"})
    print(f"[Meowser config] profile.proxy = {proxy_dict}")

    # 跟 browser.py 一样配置 webview
    config = WKWebViewConfiguration.alloc().init()
    prefs = config.preferences()
    try:
        prefs.setValue_forKey_(True, "fullScreenEnabled")
        prefs.setValue_forKey_(True, "developerExtrasEnabled")
    except Exception:
        pass

    # 应用代理（与 Meowser 一致）
    ds = WKWebsiteDataStore.defaultDataStore()
    if proxy_dict.get("type") not in ("direct", "system", None):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from proxy import apply_to_data_store as _apply
        ok = _apply(ds, proxy_dict)
        print(f"[Meowser proxy] apply_to_data_store = {ok}")
    config.setWebsiteDataStore_(ds)

    # 创建 webview
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(100, 100, 1000, 700),
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
        NSBackingStoreBuffered, False,
    )
    win.setTitle_("Meowser-loadtest")
    wv = WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, 1000, 700), config)
    try:
        wv.setCustomUserAgent_(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
        )
    except Exception:
        pass

    win.setContentView_(wv)
    win.makeKeyAndOrderFront_(None)

    URL = sys.argv[1] if len(sys.argv) > 1 else "https://translate.google.com/?hl=zh-cn"
    print(f"\n加载: {URL}")
    req = NSURLRequest.requestWithURL_(NSURL.URLWithString_(URL))
    wv.loadRequest_(req)

    # 跑 RunLoop 等加载
    deadline = time.time() + 12
    last = ""
    while time.time() < deadline:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.3))
        is_loading = wv.isLoading()
        title = str(wv.title() or "")
        url_now = str(wv.URL().absoluteString()) if wv.URL() else ""
        s = f"loading={is_loading} title={title[:30]!r} url={url_now[:80]}"
        if s != last:
            elapsed = 12 - (deadline - time.time())
            print(f"  [{elapsed:.1f}s] {s}")
            last = s
        if not is_loading and url_now and (12 - (deadline - time.time())) > 1:
            break

    print()
    print("=== 结果 ===")
    print(f"  isLoading: {wv.isLoading()}")
    print(f"  title: {wv.title()!r}")
    print(f"  URL: {wv.URL().absoluteString() if wv.URL() else 'None'}")
    if wv.title():
        print("\n✓ 加载成功")
        sys.exit(0)
    else:
        print("\n✗ 加载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
