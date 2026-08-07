"""
独立 WKWebView 测试 — 不经 Meowser 任何代码，
验证 PyObjC + WKWebView 本身能否加载 Google Translate
"""
import sys, time
from AppKit import (
    NSApplication, NSWindow, NSMakeRect, NSBackingStoreBuffered,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
)
from WebKit import WKWebView, WKWebViewConfiguration
from Foundation import NSURL, NSURLRequest, NSRunLoop, NSDate

app = NSApplication.sharedApplication()
win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    NSMakeRect(100, 100, 1000, 700),
    NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
    NSBackingStoreBuffered, False,
)
win.setTitle_("WKWebView Test")
cfg = WKWebViewConfiguration.alloc().init()
wv = WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, 1000, 700), cfg)
win.setContentView_(wv)
win.makeKeyAndOrderFront_(None)

URL = sys.argv[1] if len(sys.argv) > 1 else "https://translate.google.com/?hl=zh-cn"
print(f"加载: {URL}")
req = NSURLRequest.requestWithURL_(NSURL.URLWithString_(URL))
wv.loadRequest_(req)

# 跑 RunLoop 等加载完成
deadline = time.time() + 15
last_status = ""
while time.time() < deadline:
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.3))
    is_loading = wv.isLoading()
    title = str(wv.title() or "")
    url_now = str(wv.URL().absoluteString()) if wv.URL() else ""
    status = f"loading={is_loading} title={title[:40]!r} url={url_now[:80]}"
    if status != last_status:
        print(f"  [{time.time()-deadline+15:.1f}s] {status}")
        last_status = status
    if not is_loading and url_now and time.time() > deadline - 12:
        print("✓ 加载完成")
        break

# 最终状态
print()
print("=== 最终状态 ===")
print(f"  isLoading: {wv.isLoading()}")
print(f"  title: {wv.title()!r}")
print(f"  URL: {wv.URL().absoluteString() if wv.URL() else 'None'}")
print(f"  canGoBack: {wv.canGoBack()}")
