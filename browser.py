"""
Meowser — 核心浏览器窗口
- 大窗模式：1:1 WKWebView + 顶部地址栏（地址栏有 ⊟ 收起按钮）
- 小窗模式：webview 放入缩放容器内，CALayer transform 整页等比缩小
"""

import objc
from AppKit import (
    NSWindow, NSView, NSApplication, NSScreen,
    NSBorderlessWindowMask, NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSFloatingWindowLevel, NSColor,
    NSMenu, NSMenuItem, NSAlertFirstButtonReturn,
    NSAlert, NSTextField, NSMakeRect,
    NSFont, NSBezelStyleRoundRect, NSButton, NSSlider, NSTextAlignmentRight,
)
from WebKit import WKWebView, WKWebViewConfiguration, WKPreferences
from Foundation import NSURLRequest, NSURL, NSObject, NSNumber, NSNotificationCenter, NSBundle
from Quartz import CATransform3DMakeScale, CATransform3DIdentity

from AppKit import NSEvent
import os, sys


def _home_url():
    """返回打包后的 home.html 文件 URL"""
    bundle_path = NSBundle.mainBundle().pathForResource_ofType_("home", "html")
    if bundle_path:
        return "file://" + bundle_path
    # 开发模式 fallback
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "resources", "home.html")
    return "file://" + p


def _screen_under_cursor():
    """返回鼠标光标所在的屏幕；没有则返回主屏"""
    mouse = NSEvent.mouseLocation()
    for scr in NSScreen.screens():
        f = scr.frame()
        if (f.origin.x <= mouse.x <= f.origin.x + f.size.width and
                f.origin.y <= mouse.y <= f.origin.y + f.size.height):
            return scr
    return NSScreen.mainScreen()

# ── 尺寸常量 ─────────────────────────────────────────
SMALL_W, SMALL_H = 200, 150  # 默认值，运行时被 self._small_w/h 覆盖
BIG_W, BIG_H = 1200, 800
DESKTOP_W, DESKTOP_H = 1200, 900
ADDRESS_BAR_H = 36


class DragView(NSView):
    """可拖拽 + 双击 toggle + 右键菜单"""

    def initWithFrame_window_(self, frame, window):
        self = objc.super(DragView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._window_ref = window
        self._drag_origin = None
        return self

    def mouseDown_(self, event):
        if event.clickCount() == 2:
            self._window_ref.toggleZoom()
            self._drag_origin = None
            return
        self._drag_origin = event.locationInWindow()

    def mouseDragged_(self, event):
        if self._drag_origin is None:
            return
        win = self.window()
        loc = event.locationInWindow()
        origin = win.frame().origin
        dx = loc.x - self._drag_origin.x
        dy = loc.y - self._drag_origin.y
        win.setFrameOrigin_((origin.x + dx, origin.y + dy))

    def mouseUp_(self, event):
        self._drag_origin = None

    def rightMouseDown_(self, event):
        if hasattr(self._window_ref, 'showContextMenu_'):
            self._window_ref.showContextMenu_(event)


class AddressFieldDelegate(NSObject):
    def initWithWindow_(self, window):
        self = objc.super(AddressFieldDelegate, self).init()
        if self is None:
            return None
        self._window = window
        return self

    def control_textView_doCommandBySelector_(self, control, textView, selector):
        if selector == "insertNewline:":
            url = control.stringValue()
            if url:
                self._window.navigateTo_(url)
            return True
        return False


class NavDelegate(NSObject):
    """WKNavigationDelegate
    1) 把 URL 中嵌入的 user:pass 抽出存进 NSURLCredentialStorage，用 clean URL 导航
    2) 触发系统 Basic Auth 弹窗时自动应答（如果存了凭据）
    3) 失败时打印日志（不静默吞）
    """

    def initWithWindow_(self, window):
        self = objc.super(NavDelegate, self).init()
        if self is None:
            return None
        self._win = window
        return self

    # ⚠ 不实现 decidePolicyForNavigationAction —— 让 WKWebView 默认 allow 所有
    # （之前实现这个方法时，PyObjC 调用 decisionHandler 偶发不生效，导致所有导航被默认 cancel）

    # 处理 401/Basic Auth + 自签证书：内网链接不在乎证书，统一信任
    def webView_didReceiveAuthenticationChallenge_completionHandler_(self, webview, challenge, completion_handler):
        from Foundation import NSLog, NSURLCredentialStorage, NSURLCredential
        try:
            space = challenge.protectionSpace()
            method = str(space.authenticationMethod())

            # ─── 服务器证书校验：直接信任（内网自签 / 证书过期都放行） ───
            if method == "NSURLAuthenticationMethodServerTrust":
                trust = space.serverTrust()
                cred = NSURLCredential.credentialForTrust_(trust)
                completion_handler(0, cred)  # UseCredential
                return

            # ─── Basic / Digest Auth：用 storage 里的凭据 ───
            if method in ("NSURLAuthenticationMethodHTTPBasic", "NSURLAuthenticationMethodHTTPDigest"):
                storage = NSURLCredentialStorage.sharedCredentialStorage()
                creds = storage.credentialsForProtectionSpace_(space) or {}
                if creds:
                    first_user = list(creds.keys())[0]
                    saved = creds.objectForKey_(first_user)
                    completion_handler(0, saved)
                    return
                # 没存凭据 → 让 WebKit 弹自己的输入框
                completion_handler(1, None)
                return

            # 其他类型：默认处理
            completion_handler(1, None)
        except Exception as e:
            NSLog(f"NavDelegate auth err: {e}")
            try:
                completion_handler(1, None)
            except Exception:
                pass

    # 加载完成：把当前 URL 同步到地址栏
    def webView_didFinishNavigation_(self, webview, navigation):
        try:
            url = webview.URL()
            if url is None:
                return
            url_str = str(url.absoluteString())
            # 不同步 file:// 首页（避免显示 file:///.../home.html 难看）
            if url_str.startswith("file://"):
                self._win._address_field.setStringValue_("")
                return
            self._win._address_field.setStringValue_(url_str)
        except Exception:
            pass

    # 也响应 commit 阶段
    def webView_didCommitNavigation_(self, webview, navigation):
        self.webView_didFinishNavigation_(webview, navigation)

    # 加载失败：显示明显的错误页面（替代黑屏）
    def webView_didFailProvisionalNavigation_withError_(self, webview, navigation, error):
        self._show_error_page(webview, error)

    def webView_didFailNavigation_withError_(self, webview, navigation, error):
        self._show_error_page(webview, error)

    def _show_error_page(self, webview, error):
        from Foundation import NSLog
        try:
            desc = str(error.localizedDescription()) if error else "未知错误"
            code = error.code() if error else 0
            url = ""
            try:
                url = str(error.userInfo().get("NSErrorFailingURLStringKey", "") or "")
            except Exception:
                pass
            NSLog(f"❌ 加载失败 code={code} url={url} : {desc}")
            # 跳过 -999 (cancelled — 通常是用户/重定向)
            if code == -999:
                return
            html = self._error_html(desc, code, url)
            webview.loadHTMLString_baseURL_(html, None)
        except Exception as e:
            NSLog(f"_show_error_page exception: {e}")

    @staticmethod
    def _error_html(desc, code, url):
        # 友好错误页 — 帮用户判断是网络 / 代理 / 内网 VPN 问题
        import html as _h
        hint = ""
        if code == -1003 or "host" in desc.lower():
            hint = "⚠️ 域名解析失败 — 检查网络/DNS"
        elif code == -1004:
            hint = "⚠️ 无法连接到主机 — 内网 IP 需要 VPN/代理；或代理 (Clash/V2Ray) 没启动"
        elif code == -1001:
            hint = "⚠️ 连接超时 — 代理或 VPN 不通"
        elif code == -1200 or "ssl" in desc.lower() or "secure" in desc.lower():
            hint = "⚠️ 证书问题 — 网站证书不受信任"
        elif code == 401:
            hint = "⚠️ 需要账号密码登录"
        elif code == -1009:
            hint = "⚠️ 没有联网 — 检查 Wi-Fi"
        else:
            hint = "提示：内网链接需先连 VPN 或在「工作」profile 配置代理（Clash/V2Ray 必须运行）"

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>加载失败</title>
<style>
  body {{ font-family:-apple-system,sans-serif; background:#1c1c1e; color:#f5f5f7; margin:0;
         display:flex; align-items:center; justify-content:center; min-height:100vh; padding:40px; }}
  .box {{ max-width:560px; background:#2c2c2e; border-radius:14px; padding:32px; }}
  h1 {{ font-size:20px; margin:0 0 8px; color:#ff9500; }}
  .url {{ font-family:ui-monospace,monospace; font-size:12px; color:#98989d; word-break:break-all;
          padding:10px 12px; background:rgba(255,255,255,0.05); border-radius:6px; margin:14px 0; }}
  .desc {{ font-size:14px; color:#d1d1d6; margin-bottom:14px; line-height:1.6; }}
  .hint {{ font-size:13px; color:#ffd60a; padding:12px 14px; background:rgba(255,214,10,0.08);
           border-left:3px solid #ffd60a; border-radius:4px; margin-top:14px; line-height:1.6; }}
  .code {{ font-family:ui-monospace,monospace; font-size:11px; color:#636366; margin-top:18px; }}
</style></head>
<body><div class="box">
  <h1>无法加载页面</h1>
  <div class="desc">{_h.escape(desc)}</div>
  <div class="url">🔗 {_h.escape(url) if url else '(URL 未知)'}</div>
  <div class="hint">{hint}</div>
  <div class="code">错误码 {code}</div>
</div></body></html>"""


class StealthWindow(NSWindow):
    def initWithApp_(self, app_delegate):
        # 从 config 读取小窗尺寸
        try:
            sz = app_delegate.config().get("small_window_size", {})
            sw = int(sz.get("w", SMALL_W))
            sh = int(sz.get("h", SMALL_H))
        except Exception:
            sw, sh = SMALL_W, SMALL_H

        # 在光标所在屏幕的右下角显示
        screen_frame = _screen_under_cursor().frame()
        x = screen_frame.origin.x + screen_frame.size.width - sw - 20
        y = screen_frame.origin.y + 20
        frame = NSMakeRect(x, y, sw, sh)

        self = objc.super(StealthWindow, self).initWithContentRect_styleMask_backing_defer_(
            frame, NSBorderlessWindowMask, 2, False,
        )
        if self is None:
            return None

        self._app_delegate = app_delegate
        self._is_big = False
        self._small_w = sw
        self._small_h = sh
        self._small_frame = frame
        self._alpha = 1.0

        self.setLevel_(NSFloatingWindowLevel)
        self.setOpaque_(False)
        self.setBackgroundColor_(NSColor.clearColor())
        self.setHasShadow_(True)
        self.setMovableByWindowBackground_(False)
        self.setAlphaValue_(self._alpha)
        self.setAcceptsMouseMovedEvents_(True)
        self.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)

        # ── 根容器（圆角） ─────────────────────────
        self._container = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, self._small_w, self._small_h)
        )
        self._container.setWantsLayer_(True)
        self._container.layer().setCornerRadius_(8.0)
        self._container.layer().setMasksToBounds_(True)
        self._container.layer().setBorderWidth_(0.5)
        self._container.layer().setBorderColor_(
            NSColor.colorWithWhite_alpha_(0.3, 0.5).CGColor()
        )
        self._container.layer().setBackgroundColor_(NSColor.whiteColor().CGColor())
        self.setContentView_(self._container)

        # ── webview 缩放容器（中间层，对它做 transform）──
        self._zoom_host = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, DESKTOP_W, DESKTOP_H)
        )
        self._zoom_host.setWantsLayer_(True)
        self._zoom_host.layer().setMasksToBounds_(True)
        self._container.addSubview_(self._zoom_host)

        # ── WKWebView（1:1 填满 zoom_host）──────────
        config = WKWebViewConfiguration.alloc().init()
        prefs = config.preferences()
        # 启用 HTML5 视频全屏（YouTube/B站 全屏按钮可用）
        try:
            prefs.setValue_forKey_(True, "fullScreenEnabled")
        except Exception:
            pass
        try:
            prefs.setValue_forKey_(True, "developerExtrasEnabled")
        except Exception:
            pass
        # 媒体自动播放需要用户手势
        try:
            config.setValue_forKey_(False, "mediaTypesRequiringUserActionForPlayback")
        except Exception:
            pass

        # ── 代理：根据 profile.proxy 配置 WKWebsiteDataStore ──
        try:
            from WebKit import WKWebsiteDataStore
            ds = WKWebsiteDataStore.defaultDataStore()
            cfg_dict = app_delegate.config() if app_delegate else {}
            proxy_dict = (cfg_dict.get("profile", {}) or {}).get("proxy", {"type": "direct"})
            if proxy_dict.get("type") not in ("direct", "system", None):
                from proxy import apply_to_data_store as _apply_proxy
                _apply_proxy(ds, proxy_dict)
            config.setWebsiteDataStore_(ds)
        except Exception as e:
            from Foundation import NSLog
            NSLog(f"proxy bind error: {e}")

        # ⚠ 反检测脚本暂时禁用 — 之前怀疑它干扰了 file:// 页面的 click 事件
        # 后续要再加，必须用 forMainFrameOnly=True 且只对 https 页面生效

        self._webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, DESKTOP_W, DESKTOP_H), config
        )
        # 伪装成 Safari（Google 对 Safari 比 Chrome 宽松）
        try:
            self._webview.setCustomUserAgent_(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/18.1 Safari/605.1.15"
            )
        except Exception:
            pass
        # 绑 NavigationDelegate（不实现 decidePolicy，只处理 fail/auth → 不会吞掉 click）
        try:
            self._nav_delegate = NavDelegate.alloc().initWithWindow_(self)
            self._webview.setNavigationDelegate_(self._nav_delegate)
        except Exception as e:
            from Foundation import NSLog
            NSLog(f"setNavigationDelegate err: {e}")
        self._zoom_host.addSubview_(self._webview)

        # ── 小窗拖拽遮罩（小窗模式覆盖 webview）──────
        self._drag_overlay = DragView.alloc().initWithFrame_window_(
            NSMakeRect(0, 0, self._small_w, self._small_h), self
        )
        self._container.addSubview_(self._drag_overlay)

        # 小窗模式：顶部 18px 显示 profile 名（拖拽 + 标识）
        self._small_titlebar = NSView.alloc().initWithFrame_(
            NSMakeRect(0, self._small_h - 18, self._small_w, 18)
        )
        self._small_titlebar.setWantsLayer_(True)
        self._small_titlebar.layer().setBackgroundColor_(self._theme_solid(self._theme).CGColor())
        # profile 名字
        try:
            cfg_for_name = app_delegate.config() if app_delegate else {}
            profile = cfg_for_name.get("profile", {}) or {}
            label_text = f"{profile.get('emoji', '🐱')} {profile.get('name', '默认')}"
        except Exception:
            label_text = "🐱"
        self._small_title_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(6, 1, self._small_w - 12, 16)
        )
        self._small_title_label.setBezeled_(False)
        self._small_title_label.setDrawsBackground_(False)
        self._small_title_label.setEditable_(False)
        self._small_title_label.setSelectable_(False)
        self._small_title_label.setStringValue_(label_text)
        self._small_title_label.setFont_(NSFont.boldSystemFontOfSize_(11))
        self._small_title_label.setTextColor_(NSColor.whiteColor())
        self._small_titlebar.addSubview_(self._small_title_label)
        self._container.addSubview_(self._small_titlebar)

        # ── 地址栏（大窗模式顶部） ─────────────────
        self._address_bar = DragView.alloc().initWithFrame_window_(
            NSMakeRect(0, 0, self._small_w, ADDRESS_BAR_H), self
        )
        self._address_bar.setWantsLayer_(True)
        # 按 profile.theme 给地址栏底色
        self._theme = "yellow"
        try:
            cfg_for_theme = app_delegate.config() if app_delegate else {}
            self._theme = (cfg_for_theme.get("profile", {}) or {}).get("theme", "yellow")
        except Exception:
            pass
        bar_bg = self._theme_addr_bg(self._theme)
        self._address_bar.layer().setBackgroundColor_(bar_bg.CGColor())
        self._address_bar.setHidden_(True)
        self._container.addSubview_(self._address_bar)
        # 主题色底部 stripe（3px 高）+ 给容器加同色边框
        self._theme_stripe = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self._small_w, 3))
        self._theme_stripe.setWantsLayer_(True)
        self._theme_stripe.layer().setBackgroundColor_(self._theme_solid(self._theme).CGColor())
        self._theme_stripe.setHidden_(True)
        self._container.addSubview_(self._theme_stripe)
        # 容器边框 3px 主题色实色（明显标识 profile）
        try:
            self._container.layer().setBorderColor_(self._theme_solid(self._theme).CGColor())
            self._container.layer().setBorderWidth_(3.0)
        except Exception:
            pass

        self._back_btn   = self._make_button("←", 4, 6, 36, 24, "doBack:")
        self._fwd_btn    = self._make_button("→", 44, 6, 36, 24, "doForward:")
        self._shrink_btn = self._make_button("缩小", 4, 6, 50, 24, "doShrink:")
        self._home_btn   = self._make_button("首页", 0, 6, 50, 24, "doHome:")
        self._newwin_btn = self._make_button("⊕ 新窗口", 0, 6, 80, 24, "doNewWindow:")
        self._rearr_btn  = self._make_button("整理", 0, 6, 50, 24, "doRearrange:")
        self._pin_btn    = self._make_button("📌", 0, 6, 32, 24, "doTogglePin:")
        self._chrome_btn = self._make_button("🌐 Chrome", 0, 6, 90, 24, "doOpenInChrome:")
        self._search_btn = self._make_button("查询", 0, 6, 60, 24, "doSearch:")
        self._address_bar.addSubview_(self._back_btn)
        self._address_bar.addSubview_(self._fwd_btn)
        self._address_bar.addSubview_(self._shrink_btn)
        self._address_bar.addSubview_(self._home_btn)
        self._address_bar.addSubview_(self._newwin_btn)
        self._address_bar.addSubview_(self._rearr_btn)
        self._address_bar.addSubview_(self._pin_btn)
        self._address_bar.addSubview_(self._chrome_btn)
        self._address_bar.addSubview_(self._search_btn)
        # 置顶状态：跟着窗口创建时一直 ON（NSFloatingWindowLevel）
        self._pinned = True

        self._address_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(48, 5, self._small_w - 80, 22)
        )
        # 地址栏：浅色背景 + 深色文字（无论暗色 chrome 都清楚）
        self._address_field.setBezeled_(False)
        self._address_field.setDrawsBackground_(True)
        self._address_field.setBackgroundColor_(NSColor.whiteColor())
        self._address_field.setTextColor_(NSColor.colorWithWhite_alpha_(0.10, 1.0))
        self._address_field.setFont_(NSFont.systemFontOfSize_(13))
        self._address_field.setStringValue_("")
        self._address_field.setPlaceholderString_("输入网址或搜索关键词，回车")
        self._address_field.setWantsLayer_(True)
        self._address_field.layer().setCornerRadius_(6)
        self._address_field.layer().setBorderWidth_(0.5)
        self._address_field.layer().setBorderColor_(NSColor.colorWithWhite_alpha_(0, 0.15).CGColor())
        # 回车提交（target/action 是 NSTextField 最可靠的方式）
        self._address_field.setTarget_(self)
        self._address_field.setAction_("doSearch:")
        # 兼容性 delegate 也保留
        self._address_delegate = AddressFieldDelegate.alloc().initWithWindow_(self)
        self._address_field.setDelegate_(self._address_delegate)
        self._address_bar.addSubview_(self._address_field)

        # ── 透明度控件（地址栏右侧）─────────────────
        self._opacity_label = self._make_label("透明度", 12)
        self._opacity_label.setAlignment_(NSTextAlignmentRight)
        self._address_bar.addSubview_(self._opacity_label)

        self._opacity_slider = NSSlider.alloc().initWithFrame_(NSMakeRect(0, 0, 130, 22))
        self._opacity_slider.setMinValue_(0.2)
        self._opacity_slider.setMaxValue_(1.0)
        self._opacity_slider.setDoubleValue_(self._alpha)
        self._opacity_slider.setTarget_(self)
        self._opacity_slider.setAction_("onSliderChange:")
        self._opacity_slider.setContinuous_(True)
        self._address_bar.addSubview_(self._opacity_slider)

        self._opacity_value = self._make_label("100%", 11)
        self._address_bar.addSubview_(self._opacity_value)

        self._apply_layout(small=True)
        # 默认加载摸鱼导航首页
        self.goHome()

        # 自己作为代理 — 监听失焦
        self.setDelegate_(self)
        return self

    # ── 失焦自动缩回 ───────────────────────────
    def windowDidResignKey_(self, notification):
        if self._is_big and not getattr(self, "_suppress_resign", False):
            # 延迟一下避免 modal 刚刚弹出又消失的边缘情况
            self.performSelector_withObject_afterDelay_("_autoShrinkIfNeeded:", None, 0.1)

    def _autoShrinkIfNeeded_(self, _):
        if self._is_big and not self.isKeyWindow():
            self.toggleZoom()

    # ── 主题色辅助 ─────────────────────────
    @staticmethod
    def _theme_solid(theme):
        from AppKit import NSColor
        m = {
            "red":    NSColor.colorWithRed_green_blue_alpha_(255/255.0,  59/255.0,  48/255.0, 1.0),
            "green":  NSColor.colorWithRed_green_blue_alpha_( 52/255.0, 199/255.0,  89/255.0, 1.0),
            "yellow": NSColor.colorWithRed_green_blue_alpha_(255/255.0, 204/255.0,   0/255.0, 1.0),
        }
        return m.get(theme, m["yellow"])

    @staticmethod
    def _theme_addr_bg(theme):
        """地址栏背景色：统一深灰，theme 信息只放底部 stripe"""
        from AppKit import NSColor
        return NSColor.colorWithRed_green_blue_alpha_(38/255.0, 38/255.0, 42/255.0, 1.0)

    def _make_button(self, title, x, y, w, h, action):
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
        btn.setTitle_(title)
        btn.setBezelStyle_(11)
        btn.setBordered_(True)
        btn.setFont_(NSFont.systemFontOfSize_(12))
        btn.setAlignment_(2)
        try: btn.cell().setAlignment_(2)
        except Exception: pass
        btn.setTarget_(self)
        btn.setAction_(action)
        return btn

    def _make_label(self, text, size):
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 50, 22))
        lbl.setStringValue_(text)
        lbl.setBezeled_(False)
        lbl.setDrawsBackground_(False)
        lbl.setEditable_(False)
        lbl.setSelectable_(False)
        lbl.setFont_(NSFont.systemFontOfSize_(size))
        lbl.setTextColor_(NSColor.colorWithWhite_alpha_(0.2, 1.0))
        return lbl

    @objc.IBAction
    def onSliderChange_(self, sender):
        v = sender.doubleValue()
        self.setOpacityLevel_(v)
        self._opacity_value.setStringValue_(f"{int(v * 100)}%")

    def _apply_layout(self, small):
        if small:
            # 小窗：zoom_host 从 1200x900 缩放 scale 后嵌入 200x150
            self._container.setFrame_(NSMakeRect(0, 0, self._small_w, self._small_h))

            scale = min(self._small_w / float(DESKTOP_W), self._small_h / float(DESKTOP_H))
            tx = (self._small_w - DESKTOP_W * scale) / 2.0
            ty = (self._small_h - DESKTOP_H * scale) / 2.0

            # 对中间容器做 transform — WKWebView 跟随容器一起缩放
            self._zoom_host.setFrame_(NSMakeRect(0, 0, DESKTOP_W, DESKTOP_H))
            host_layer = self._zoom_host.layer()
            host_layer.setAnchorPoint_((0, 0))
            host_layer.setPosition_((tx, ty))
            host_layer.setTransform_(CATransform3DMakeScale(scale, scale, 1.0))

            self._drag_overlay.setFrame_(NSMakeRect(0, 0, self._small_w, self._small_h))
            self._drag_overlay.setHidden_(False)
            self._address_bar.setHidden_(True)
            # 小窗顶部 profile 标签
            if hasattr(self, "_small_titlebar"):
                self._small_titlebar.setFrame_(NSMakeRect(0, self._small_h - 18, self._small_w, 18))
                self._small_title_label.setFrame_(NSMakeRect(6, 1, self._small_w - 12, 16))
                self._small_titlebar.setHidden_(False)
                # 提到最上层（drag_overlay 之下让点击仍能拖动）
                try:
                    self._small_titlebar.removeFromSuperview()
                    self._container.addSubview_(self._small_titlebar)
                except Exception:
                    pass
            # 小窗模式隐藏透明度控件 + 查询按钮
            self._opacity_label.setHidden_(True)
            self._opacity_slider.setHidden_(True)
            self._opacity_value.setHidden_(True)
            if hasattr(self, "_search_btn"):
                self._search_btn.setHidden_(True)
            if hasattr(self, "_home_btn"):
                self._home_btn.setHidden_(True)
            if hasattr(self, "_newwin_btn"):
                self._newwin_btn.setHidden_(True)
            if hasattr(self, "_rearr_btn"):
                self._rearr_btn.setHidden_(True)
            if hasattr(self, "_pin_btn"):
                self._pin_btn.setHidden_(True)
            if hasattr(self, "_chrome_btn"):
                self._chrome_btn.setHidden_(True)
            if hasattr(self, "_theme_stripe"):
                self._theme_stripe.setHidden_(True)
        else:
            # 大窗模式 — 隐藏小窗 titlebar
            if hasattr(self, "_small_titlebar"):
                self._small_titlebar.setHidden_(True)
            # profile 备注 — 大窗顶部状态条 22px（在地址栏之上）
            try:
                cfg_for_note = self._app_delegate.config() if self._app_delegate else {}
                profile = cfg_for_note.get("profile", {}) or {}
                pname = profile.get("name", "")
                pnote = profile.get("note", "")
                pemoji = profile.get("emoji", "🐱")
                summary = f"{pemoji} {pname}"
                if pnote:
                    summary += f"  ·  {pnote}"
                if not hasattr(self, "_profile_strip"):
                    self._profile_strip = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, BIG_W, 22))
                    self._profile_strip.setWantsLayer_(True)
                    self._profile_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(12, 3, BIG_W - 24, 16))
                    self._profile_lbl.setBezeled_(False)
                    self._profile_lbl.setDrawsBackground_(False)
                    self._profile_lbl.setEditable_(False)
                    self._profile_lbl.setSelectable_(False)
                    self._profile_lbl.setFont_(NSFont.boldSystemFontOfSize_(11))
                    self._profile_lbl.setTextColor_(NSColor.whiteColor())
                    self._profile_strip.addSubview_(self._profile_lbl)
                    self._container.addSubview_(self._profile_strip)
                self._profile_strip.layer().setBackgroundColor_(self._theme_solid(self._theme).CGColor())
                self._profile_lbl.setStringValue_(summary)
                self._profile_strip.setFrame_(NSMakeRect(0, BIG_H - 22, BIG_W, 22))
                self._profile_lbl.setFrame_(NSMakeRect(12, 3, BIG_W - 24, 16))
                self._profile_strip.setHidden_(False)
                # 提到顶层
                try:
                    self._profile_strip.removeFromSuperview()
                    self._container.addSubview_(self._profile_strip)
                except Exception:
                    pass
            except Exception:
                pass
            content_h = BIG_H - ADDRESS_BAR_H - 22  # 减去 profile strip

            self._container.setFrame_(NSMakeRect(0, 0, BIG_W, BIG_H))

            # 大窗：webview 1:1 全尺寸，无变换
            self._zoom_host.setFrame_(NSMakeRect(0, 0, BIG_W, content_h))
            host_layer = self._zoom_host.layer()
            host_layer.setAnchorPoint_((0, 0))
            host_layer.setPosition_((0, 0))
            host_layer.setTransform_(CATransform3DIdentity)
            self._webview.setFrame_(NSMakeRect(0, 0, BIG_W, content_h))

            self._drag_overlay.setHidden_(True)

            # 地址栏在顶部：[⊟] [◀][▶] [输入框............]
            self._address_bar.setFrame_(
                NSMakeRect(0, content_h, BIG_W, ADDRESS_BAR_H)
            )
            BTN_Y, BTN_H = 6, 24
            self._shrink_btn.setFrame_(NSMakeRect(4,   BTN_Y, 50, BTN_H))
            self._home_btn.setFrame_(NSMakeRect(58,   BTN_Y, 50, BTN_H))
            self._back_btn.setFrame_(NSMakeRect(112,  BTN_Y, 36, BTN_H))
            self._fwd_btn.setFrame_(NSMakeRect(150,   BTN_Y, 36, BTN_H))
            self._newwin_btn.setFrame_(NSMakeRect(190, BTN_Y, 80, BTN_H))
            self._rearr_btn.setFrame_(NSMakeRect(274,  BTN_Y, 50, BTN_H))
            self._pin_btn.setFrame_(NSMakeRect(328,   BTN_Y, 32, BTN_H))
            self._chrome_btn.setFrame_(NSMakeRect(364, BTN_Y, 90, BTN_H))
            self._home_btn.setHidden_(False)
            self._newwin_btn.setHidden_(False)
            self._rearr_btn.setHidden_(False)
            self._pin_btn.setHidden_(False)
            self._chrome_btn.setHidden_(False)

            # 右侧透明度区域：[透明度] [=====O=====] 100%
            opacity_value_w = 44
            slider_w = 150
            label_w = 50
            opacity_total_w = label_w + slider_w + opacity_value_w + 12
            opacity_x = BIG_W - opacity_total_w - 6

            self._opacity_label.setFrame_(NSMakeRect(opacity_x, BTN_Y, label_w, BTN_H))
            self._opacity_slider.setFrame_(NSMakeRect(opacity_x + label_w + 4, BTN_Y + 1, slider_w, BTN_H - 2))
            self._opacity_value.setFrame_(NSMakeRect(
                opacity_x + label_w + 4 + slider_w + 4, BTN_Y, opacity_value_w, BTN_H
            ))
            self._opacity_label.setHidden_(False)
            self._opacity_slider.setHidden_(False)
            self._opacity_value.setHidden_(False)

            # 地址输入框 + 查询按钮
            addr_x = 462
            search_btn_w = 60
            addr_w = opacity_x - addr_x - 8 - search_btn_w - 4
            self._address_field.setFrame_(NSMakeRect(addr_x, BTN_Y, addr_w, BTN_H))
            self._search_btn.setFrame_(NSMakeRect(addr_x + addr_w + 4, BTN_Y, search_btn_w, BTN_H))
            self._search_btn.setHidden_(False)
            self._address_bar.setHidden_(False)
            # 主题色 stripe（地址栏底部 3px）
            if hasattr(self, "_theme_stripe"):
                self._theme_stripe.setFrame_(NSMakeRect(0, content_h - 3, BIG_W, 3))
                self._theme_stripe.setHidden_(False)
                # 把 stripe 提到地址栏之上
                try:
                    self._theme_stripe.removeFromSuperview()
                    self._container.addSubview_(self._theme_stripe)
                except Exception:
                    pass

    def toggleZoom(self):
        if self._is_big:
            self.setFrame_display_animate_(self._small_frame, True, True)
            self._apply_layout(small=True)
            self._is_big = False
        else:
            self._small_frame = self.frame()
            # 居中到当前窗口所在屏幕
            cur_screen = self.screen() or _screen_under_cursor()
            sf = cur_screen.frame()
            x = sf.origin.x + (sf.size.width - BIG_W) / 2
            y = sf.origin.y + (sf.size.height - BIG_H) / 2
            big_frame = NSMakeRect(x, y, BIG_W, BIG_H)
            self.setFrame_display_animate_(big_frame, True, True)
            self._apply_layout(small=False)
            self._is_big = True
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self.makeKeyAndOrderFront_(None)

    def setSmallSizeW_h_(self, w, h):
        """运行时调整小窗尺寸；如果当前在小窗模式立即重新布局"""
        self._small_w = int(w)
        self._small_h = int(h)
        if not self._is_big:
            # 立即应用：保持窗口右下角位置不变
            cur = self.frame()
            new_x = cur.origin.x + cur.size.width - self._small_w
            new_y = cur.origin.y
            new_frame = NSMakeRect(new_x, new_y, self._small_w, self._small_h)
            self.setFrame_display_(new_frame, True)
            self._small_frame = new_frame
            self._apply_layout(small=True)

    def relocateToCursorScreen(self):
        """把小窗移到光标所在屏的右下角（重新唤起时用）"""
        if self._is_big:
            return
        sf = _screen_under_cursor().frame()
        x = sf.origin.x + sf.size.width - self._small_w - 20
        y = sf.origin.y + 20
        new_frame = NSMakeRect(x, y, self._small_w, self._small_h)
        self.setFrame_display_(new_frame, True)
        self._small_frame = new_frame

    def setOpacityLevel_(self, level):
        self._alpha = level
        self.setAlphaValue_(level)
        # 同步滑块和数值（避免菜单/右键调整后滑块不同步）
        if hasattr(self, "_opacity_slider"):
            self._opacity_slider.setDoubleValue_(level)
        if hasattr(self, "_opacity_value"):
            self._opacity_value.setStringValue_(f"{int(level * 100)}%")

    def navigateTo_(self, text):
        """智能识别：URL → 跳转，否则当作搜索关键词"""
        import urllib.parse
        s = (text or "").strip()
        if not s:
            return

        if "://" in s:
            target = s
        elif " " not in s and "." in s and not s.startswith("."):
            # 看起来是域名，比如 youtube.com
            target = "https://" + s
        else:
            # 当作搜索关键词
            target = "https://www.google.com/search?q=" + urllib.parse.quote(s)

        url = NSURL.URLWithString_(target)
        if url:
            req = NSURLRequest.requestWithURL_(url)
            self._webview.loadRequest_(req)
            self._address_field.setStringValue_(target)

    def goBack(self): self._webview.goBack()
    def goForward(self): self._webview.goForward()
    def reload(self): self._webview.reload()

    @objc.IBAction
    def doBack_(self, sender): self.goBack()
    @objc.IBAction
    def doForward_(self, sender): self.goForward()
    @objc.IBAction
    def doShrink_(self, sender): self.toggleZoom()

    @objc.IBAction
    def doHome_(self, sender): self.goHome()

    @objc.IBAction
    def doNewWindow_(self, sender):
        """开一个 Child 窗口加入当前 Boss"""
        try:
            from boss_manager import find_boss_for_window, get_active_boss
            boss = find_boss_for_window(self) or get_active_boss()
            if boss is None:
                return
            child = StealthWindow.alloc().initWithApp_(self._app_delegate)
            boss.add_child(child)
            child.makeKeyAndOrderFront_(None)
        except Exception as e:
            from Foundation import NSLog
            NSLog(f"doNewWindow_ error: {e}")

    @objc.IBAction
    def doRearrange_(self, sender):
        """整理当前 Boss 下所有窗口"""
        try:
            from boss_manager import find_boss_for_window, get_active_boss
            boss = find_boss_for_window(self) or get_active_boss()
            if boss is not None:
                boss.layout.reflow()
        except Exception as e:
            from Foundation import NSLog
            NSLog(f"doRearrange_ error: {e}")

    @objc.IBAction
    def doOpenInChrome_(self, sender):
        """大窗内键盘快捷方式：⌘⇧O 把当前页扔到 Chrome"""
        try:
            url = self._webview.URL()
            if url is None:
                return
            url_str = str(url.absoluteString())
            from AppKit import NSWorkspace
            from Foundation import NSURL
            import os
            for p in ["/Applications/Google Chrome.app",
                      "/Applications/Brave Browser.app",
                      "/Applications/Microsoft Edge.app",
                      "/Applications/Arc.app"]:
                if os.path.isdir(p):
                    target = NSURL.URLWithString_(url_str)
                    NSWorkspace.sharedWorkspace().openURLs_withApplicationAtURL_configuration_completionHandler_(
                        [target], NSURL.fileURLWithPath_(p), None, None
                    )
                    return
            import subprocess
            subprocess.Popen(["open", "-a", "Google Chrome", url_str])
        except Exception as e:
            from Foundation import NSLog
            NSLog(f"doOpenInChrome_ err: {e}")

    @objc.IBAction
    def doTogglePin_(self, sender):
        """置顶切换：浮动级别 ↔ 普通级别（用整数避免 PyObjC 常量绑定问题）"""
        from Foundation import NSLog
        try:
            self._pinned = not getattr(self, "_pinned", True)
            # NSFloatingWindowLevel = 3, NSNormalWindowLevel = 0
            new_level = 3 if self._pinned else 0
            self.setLevel_(new_level)
            if hasattr(self, "_pin_btn"):
                self._pin_btn.setTitle_("📌" if self._pinned else "📍")
            NSLog(f"📌 置顶切换: pinned={self._pinned} level={self.level()}")
        except Exception as e:
            NSLog(f"doTogglePin_ error: {e}")

    def goHome(self):
        # 由 profile.show_bookmarks 决定首页（不再按 mode 自动切换）
        try:
            cfg = self._app_delegate.config() if self._app_delegate else {}
            show_bm = bool((cfg.get("profile", {}) or {}).get("show_bookmarks", False))
        except Exception:
            show_bm = False
        if show_bm:
            try:
                from bookmarks import load_cache, import_first_available, render_work_home
                data = load_cache()
                if data is None:
                    data = import_first_available()
                home_url_str = render_work_home(data)
            except Exception as e:
                from Foundation import NSLog
                NSLog(f"goHome work mode err: {e}")
                home_url_str = _home_url()
        else:
            home_url_str = _home_url()

        url = NSURL.URLWithString_(home_url_str)
        if url:
            req = NSURLRequest.requestWithURL_(url)
            self._webview.loadRequest_(req)
            self._address_field.setStringValue_("")

    @objc.IBAction
    def doSearch_(self, sender):
        text = self._address_field.stringValue()
        if text:
            self.navigateTo_(text)

    def showContextMenu_(self, event):
        menu = NSMenu.alloc().initWithTitle_("MeowserMenu")
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("输入网址...", "menuNavigate:", "")
        item.setTarget_(self); menu.addItem_(item)
        menu.addItem_(NSMenuItem.separatorItem())
        for title, action in [("后退", "menuGoBack:"), ("前进", "menuGoForward:"), ("刷新", "menuReload:")]:
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            it.setTarget_(self); menu.addItem_(it)
        menu.addItem_(NSMenuItem.separatorItem())
        opacity_menu = NSMenu.alloc().initWithTitle_("透明度")
        for label, val in [("100%", 1.0), ("80%", 0.8), ("60%", 0.6), ("40%", 0.4), ("20%", 0.2)]:
            sub = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, "menuSetOpacity:", "")
            sub.setTarget_(self); sub.setRepresentedObject_(NSNumber.numberWithDouble_(val))
            if abs(self._alpha - val) < 0.05:
                sub.setState_(1)
            opacity_menu.addItem_(sub)
        opacity_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("透明度", None, "")
        opacity_item.setSubmenu_(opacity_menu)
        menu.addItem_(opacity_item)
        menu.addItem_(NSMenuItem.separatorItem())
        tag = "缩小窗口" if self._is_big else "放大窗口"
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(tag, "menuToggleZoom:", "")
        it.setTarget_(self); menu.addItem_(it)
        menu.addItem_(NSMenuItem.separatorItem())
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("退出", "menuQuit:", "")
        it.setTarget_(self); menu.addItem_(it)
        NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self._container)

    @objc.IBAction
    def menuNavigate_(self, sender):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("输入网址")
        alert.addButtonWithTitle_("前往")
        alert.addButtonWithTitle_("取消")
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        field.setStringValue_("https://")
        alert.setAccessoryView_(field)
        if alert.runModal() == NSAlertFirstButtonReturn:
            if field.stringValue():
                self.navigateTo_(field.stringValue())

    @objc.IBAction
    def menuGoBack_(self, sender): self.goBack()
    @objc.IBAction
    def menuGoForward_(self, sender): self.goForward()
    @objc.IBAction
    def menuReload_(self, sender): self.reload()

    @objc.IBAction
    def menuSetOpacity_(self, sender):
        v = sender.representedObject()
        if v is not None:
            self.setOpacityLevel_(float(v))

    @objc.IBAction
    def menuToggleZoom_(self, sender): self.toggleZoom()

    @objc.IBAction
    def menuQuit_(self, sender):
        NSApplication.sharedApplication().terminate_(None)

    def canBecomeKeyWindow(self): return True
    def canBecomeMainWindow(self): return True
