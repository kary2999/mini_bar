"""
Meowser — Profile 编辑窗（独立窗口，L 暗色风格）
- emoji 网格选择
- 配色色块选择
- 模式分段控件
- 代理类型 4 选 1 + 主机/端口动态
"""

import objc
from AppKit import (
    NSWindow, NSView, NSTextField, NSColor, NSFont, NSButton,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSWindowStyleMaskFullSizeContentView,
    NSBackingStoreBuffered, NSScreen, NSAppearance,
    NSAlert, NSAlertFirstButtonReturn, NSWindowTitleHidden,
    NSWindowCollectionBehaviorMoveToActiveSpace,
)
from Foundation import NSObject, NSLog, NSMakeRect, NSMakeSize


def _c(r, g, b, a=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(r/255.0, g/255.0, b/255.0, a)


# Linear/Raycast 暗色配色
BG_WIN     = _c(22, 22, 24)
BG_HEAD    = _c(28, 28, 30)
BG_INPUT   = _c(255, 255, 255, 0.04)
BG_INPUT_F = _c(74, 222, 128, 0.06)  # focus 状态
BG_FOOT    = _c(14, 14, 16)
HAIR       = _c(255, 255, 255, 0.06)
HAIR_2     = _c(255, 255, 255, 0.10)
LABEL      = _c(255, 255, 255)
LABEL_2    = _c(255, 255, 255, 0.85)
LABEL_3    = _c(255, 255, 255, 0.50)
LABEL_4    = _c(255, 255, 255, 0.35)
GREEN      = _c(74, 222, 128)
GREEN_BG   = _c(74, 222, 128, 0.10)
RED        = _c(255, 95, 87)
RED_BG     = _c(255, 95, 87, 0.10)


COLOR_OPTIONS = [
    ("fun",    [_c(255, 169, 77),  _c(255, 107, 157)]),
    ("work",   [_c(37, 99, 235),   _c(6, 182, 212)]),
    ("crypto", [_c(245, 158, 11),  _c(239, 68, 68)]),
    ("news",   [_c(16, 185, 129),  _c(20, 184, 166)]),
]

EMOJI_OPTIONS = [
    "🐱", "💻", "🎮", "📺",
    "📰", "📈", "💰", "⚙",
    "🌈", "🚀", "🎵", "📕",
    "💬", "📧", "🛒", "🎬",
]

PROXY_TYPES = ["DIRECT", "SYSTEM", "SOCKS5", "HTTP"]


def _centered(color, font):
    """生成居中的 NSAttributedString 属性字典（按钮 attributedTitle 用）"""
    from AppKit import NSMutableParagraphStyle
    ps = NSMutableParagraphStyle.alloc().init()
    ps.setAlignment_(2)  # NSTextAlignmentCenter
    return {"NSColor": color, "NSFont": font, "NSParagraphStyle": ps}


class _GradientView(NSView):
    """彩色头像/色块"""
    def initWithFrame_colors_emoji_(self, frame, color_pair, emoji):
        self = objc.super(_GradientView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.setWantsLayer_(True)
        from Quartz import CAGradientLayer
        gl = CAGradientLayer.layer()
        gl.setFrame_(self.bounds())
        gl.setColors_([color_pair[0].CGColor(), color_pair[1].CGColor()])
        gl.setStartPoint_((0, 0))
        gl.setEndPoint_((1, 1))
        gl.setCornerRadius_(frame.size.width * 0.25)
        self.layer().setCornerRadius_(frame.size.width * 0.25)
        self.layer().setMasksToBounds_(True)
        self.layer().addSublayer_(gl)
        if emoji:
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, frame.size.height))
            lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
            lbl.setEditable_(False); lbl.setSelectable_(False)
            lbl.setAlignment_(2)
            lbl.setStringValue_(emoji)
            lbl.setFont_(NSFont.systemFontOfSize_(frame.size.width * 0.5))
            lbl.setTextColor_(NSColor.whiteColor())
            lbl.setFrame_(NSMakeRect(0, -frame.size.height * 0.10, frame.size.width, frame.size.height))
            self.addSubview_(lbl)
        return self


class EditWindowController(NSObject):
    """单个 profile 的编辑窗"""

    WIDTH = 380

    def initWithProfile_onSave_onDelete_(self, profile, on_save, on_delete):
        self = objc.super(EditWindowController, self).init()
        if self is None:
            return None
        self._p = dict(profile)  # 工作副本
        self._on_save = on_save
        self._on_delete = on_delete
        self._window = None
        # 控件引用
        self._name_input = None
        self._note_input = None
        self._proxy_host = None
        self._proxy_port = None
        self._cur_emoji = self._p.get("emoji", "🐱")
        self._cur_color = self._p.get("color", "fun")
        self._cur_mode = self._p.get("mode", "work")
        self._cur_theme = self._p.get("theme", "yellow")
        self._cur_proxy = (self._p.get("proxy", {}).get("type", "direct") or "direct").lower()
        self._emoji_btns = {}
        self._color_btns = {}
        self._mode_btns = {}
        self._theme_btns = {}
        self._proxy_btns = {}
        return self

    def show(self):
        if self._window is None:
            self._build()
        # 居中
        try:
            from AppKit import NSEvent
            mouse = NSEvent.mouseLocation()
            for scr in NSScreen.screens():
                f = scr.frame()
                if f.origin.x <= mouse.x <= f.origin.x + f.size.width:
                    cx = f.origin.x + (f.size.width - self.WIDTH) / 2
                    cy = f.origin.y + (f.size.height - self._window.frame().size.height) / 2 + 50
                    self._window.setFrameOrigin_((cx, cy))
                    break
        except Exception:
            pass
        from AppKit import NSApplication
        self._window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def _build(self):
        # 估算高度：head + 3 sections + footer
        H_HEAD = 56
        H_BASIC = 130
        H_APPEARANCE = 280   # 加了主题色行
        H_NETWORK = 200   # 加了 show_bookmarks 行
        H_FOOT = 56
        total_h = H_HEAD + H_BASIC + H_APPEARANCE + H_NETWORK + H_FOOT

        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, self.WIDTH, total_h),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskFullSizeContentView,
            NSBackingStoreBuffered, False,
        )
        win.setTitle_("编辑工作区")
        win.setTitlebarAppearsTransparent_(True)
        win.setTitleVisibility_(NSWindowTitleHidden)
        win.setMovableByWindowBackground_(True)
        # 强制暗色外观
        try:
            win.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        except Exception:
            pass
        win.setBackgroundColor_(BG_WIN)

        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.WIDTH, total_h))
        content.setWantsLayer_(True)
        content.layer().setBackgroundColor_(BG_WIN.CGColor())
        win.setContentView_(content)

        # 自顶向下摆放
        y = total_h

        # ─ 头 ─
        y -= H_HEAD
        head = self._build_head(NSMakeRect(0, y, self.WIDTH, H_HEAD))
        content.addSubview_(head)

        # ─ Basic ─
        y -= H_BASIC
        basic = self._build_basic(NSMakeRect(0, y, self.WIDTH, H_BASIC))
        content.addSubview_(basic)

        # ─ Appearance ─
        y -= H_APPEARANCE
        app = self._build_appearance(NSMakeRect(0, y, self.WIDTH, H_APPEARANCE))
        content.addSubview_(app)

        # ─ Network ─
        y -= H_NETWORK
        net = self._build_network(NSMakeRect(0, y, self.WIDTH, H_NETWORK))
        content.addSubview_(net)

        # ─ Footer ─
        y -= H_FOOT
        foot = self._build_footer(NSMakeRect(0, y, self.WIDTH, H_FOOT))
        content.addSubview_(foot)

        self._window = win

    # ── helpers ─────────────────────────
    def _make_label(self, text, x, y, w, font_size=10, color=None, mono=True, bold=True):
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, 14))
        lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
        lbl.setEditable_(False); lbl.setSelectable_(False)
        lbl.setStringValue_(text)
        if mono and bold:
            lbl.setFont_(NSFont.fontWithName_size_("SF Mono Bold", font_size) or NSFont.boldSystemFontOfSize_(font_size))
        elif mono:
            lbl.setFont_(NSFont.fontWithName_size_("SF Mono", font_size) or NSFont.systemFontOfSize_(font_size))
        elif bold:
            lbl.setFont_(NSFont.boldSystemFontOfSize_(font_size))
        else:
            lbl.setFont_(NSFont.systemFontOfSize_(font_size))
        lbl.setTextColor_(color or LABEL_4)
        return lbl

    def _make_input(self, x, y, w, h, value, placeholder=""):
        f = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
        f.setBezeled_(False)
        f.setDrawsBackground_(True)
        f.setBackgroundColor_(BG_INPUT)
        f.setStringValue_(value or "")
        f.setPlaceholderString_(placeholder)
        f.setFont_(NSFont.systemFontOfSize_(12))
        f.setTextColor_(LABEL)
        f.setWantsLayer_(True)
        f.layer().setCornerRadius_(5)
        f.layer().setBorderWidth_(0.5)
        f.layer().setBorderColor_(HAIR_2.CGColor())
        return f

    def _build_head(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_HEAD.CGColor())
        # 小标题
        h_icon = NSTextField.alloc().initWithFrame_(NSMakeRect(20, frame.size.height - 36, 22, 22))
        h_icon.setBezeled_(False); h_icon.setDrawsBackground_(False)
        h_icon.setEditable_(False); h_icon.setSelectable_(False)
        h_icon.setStringValue_("⚙")
        h_icon.setFont_(NSFont.systemFontOfSize_(14))
        h_icon.setTextColor_(LABEL)
        v.addSubview_(h_icon)
        h_title = NSTextField.alloc().initWithFrame_(NSMakeRect(46, frame.size.height - 38, 200, 24))
        h_title.setBezeled_(False); h_title.setDrawsBackground_(False)
        h_title.setEditable_(False); h_title.setSelectable_(False)
        h_title.setStringValue_("EDIT WORKSPACE")
        h_title.setFont_(NSFont.fontWithName_size_("SF Mono Bold", 13) or NSFont.boldSystemFontOfSize_(13))
        h_title.setTextColor_(LABEL)
        v.addSubview_(h_title)
        # id 副标
        h_sub = NSTextField.alloc().initWithFrame_(NSMakeRect(46, frame.size.height - 54, 280, 16))
        h_sub.setBezeled_(False); h_sub.setDrawsBackground_(False)
        h_sub.setEditable_(False); h_sub.setSelectable_(False)
        h_sub.setStringValue_(f"id: {self._p.get('id', '')}")
        h_sub.setFont_(NSFont.fontWithName_size_("SF Mono", 10) or NSFont.systemFontOfSize_(10))
        h_sub.setTextColor_(LABEL_4)
        v.addSubview_(h_sub)
        # 底部分隔线
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)
        return v

    def _build_basic(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_WIN.CGColor())
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)

        # name
        v.addSubview_(self._make_label("name", 20, frame.size.height - 24, 100, 10, LABEL_4))
        self._name_input = self._make_input(20, frame.size.height - 56, frame.size.width - 40, 28,
                                             self._p.get("name", ""), "工作区名字")
        v.addSubview_(self._name_input)

        # note
        v.addSubview_(self._make_label("note", 20, frame.size.height - 86, 100, 10, LABEL_4))
        self._note_input = self._make_input(20, frame.size.height - 118, frame.size.width - 40, 28,
                                             self._p.get("note", ""), "一句话备注")
        v.addSubview_(self._note_input)
        return v

    def _build_appearance(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_WIN.CGColor())
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)

        # emoji
        v.addSubview_(self._make_label("emoji", 20, frame.size.height - 24, 100, 10, LABEL_4))
        # 8 列网格
        cols = 8
        cell = (frame.size.width - 40 - (cols - 1) * 4) / cols
        gx = 20; gy = frame.size.height - 30 - cell
        for i, em in enumerate(EMOJI_OPTIONS):
            row = i // cols
            col = i % cols
            x = gx + col * (cell + 4)
            y = gy - row * (cell + 4)
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, cell, cell))
            btn.setTitle_(em)
            btn.setBordered_(False)
            btn.setFont_(NSFont.systemFontOfSize_(cell * 0.5))
            btn.setWantsLayer_(True)
            self._style_emoji_btn(btn, em == self._cur_emoji)
            btn.setTarget_(self); btn.setAction_("pickEmoji:")
            # 用 tag 存索引
            btn.setTag_(i)
            v.addSubview_(btn)
            self._emoji_btns[em] = btn

        # color
        v.addSubview_(self._make_label("color", 20, gy - 2 * (cell + 4) - 14, 100, 10, LABEL_4))
        cy_color = gy - 2 * (cell + 4) - 44
        for i, (name, pair) in enumerate(COLOR_OPTIONS):
            cx = 20 + i * 36
            chip = _GradientView.alloc().initWithFrame_colors_emoji_(
                NSMakeRect(cx, cy_color, 28, 28), pair, ""
            )
            v.addSubview_(chip)
            # 透明按钮覆盖
            ovr = NSButton.alloc().initWithFrame_(NSMakeRect(cx, cy_color, 28, 28))
            ovr.setTitle_("")
            ovr.setBordered_(False)
            ovr.setTransparent_(True)
            ovr.setTarget_(self); ovr.setAction_("pickColor:")
            ovr.setTag_(i)
            v.addSubview_(ovr)
            self._color_btns[name] = (chip, ovr)
            # 选中边框
            if name == self._cur_color:
                chip.layer().setBorderWidth_(2)
                chip.layer().setBorderColor_(LABEL.CGColor())

        # mode
        mode_y = cy_color - 38
        v.addSubview_(self._make_label("mode", 20, mode_y + 22, 100, 10, LABEL_4))
        # 分段控件 2 选 1
        mb_w = (frame.size.width - 40 - 4) / 2
        for i, (name, label) in enumerate([("work", "⚒️ work"), ("slack", "🌈 slack")]):
            x = 20 + i * (mb_w + 4)
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, mode_y - 8, mb_w, 28))
            btn.setTitle_(label)
            btn.setBordered_(False)
            btn.setFont_(NSFont.systemFontOfSize_(12))
            btn.setAlignment_(2)
            btn.setWantsLayer_(True)
            self._style_seg_btn(btn, name == self._cur_mode)
            btn.setTarget_(self); btn.setAction_("pickMode:")
            btn.setTag_(i)
            v.addSubview_(btn)
            self._mode_btns[name] = btn

        # theme（主题色 — 红/绿/黄）
        theme_y = mode_y - 50
        v.addSubview_(self._make_label("theme · 浏览器配色", 20, theme_y + 22, 200, 10, LABEL_4))
        themes = [("red", _c(255, 59, 48)),
                  ("green", _c(52, 199, 89)),
                  ("yellow", _c(255, 204, 0))]
        chip_w = 50
        for i, (name, color) in enumerate(themes):
            x = 20 + i * (chip_w + 8)
            chip = NSView.alloc().initWithFrame_(NSMakeRect(x, theme_y - 8, chip_w, 28))
            chip.setWantsLayer_(True)
            chip.layer().setBackgroundColor_(color.CGColor())
            chip.layer().setCornerRadius_(6)
            if name == self._cur_theme:
                chip.layer().setBorderWidth_(2.5)
                chip.layer().setBorderColor_(LABEL.CGColor())
            v.addSubview_(chip)
            ovr = NSButton.alloc().initWithFrame_(NSMakeRect(x, theme_y - 8, chip_w, 28))
            ovr.setTitle_("")
            ovr.setBordered_(False)
            ovr.setTransparent_(True)
            ovr.setTarget_(self); ovr.setAction_("pickTheme:")
            ovr.setTag_(i)
            v.addSubview_(ovr)
            self._theme_btns[name] = (chip, ovr)
        return v

    def _build_network(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_WIN.CGColor())
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)

        # proxy type
        v.addSubview_(self._make_label("proxy type", 20, frame.size.height - 24, 100, 10, LABEL_4))
        cell_w = (frame.size.width - 40 - 3 * 4) / 4
        for i, t in enumerate(PROXY_TYPES):
            x = 20 + i * (cell_w + 4)
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, frame.size.height - 60, cell_w, 30))
            btn.setTitle_(t)
            btn.setBordered_(False)
            btn.setFont_(NSFont.fontWithName_size_("SF Mono Bold", 11) or NSFont.boldSystemFontOfSize_(11))
            btn.setWantsLayer_(True)
            self._style_proxy_btn(btn, t.lower() == self._cur_proxy.lower())
            btn.setTarget_(self); btn.setAction_("pickProxyType:")
            btn.setTag_(i)
            v.addSubview_(btn)
            self._proxy_btns[t.lower()] = btn

        # host / port
        cur_host = self._p.get("proxy", {}).get("host", "")
        cur_port = str(self._p.get("proxy", {}).get("port", "") or "")
        host_w = frame.size.width - 40 - 60 - 4
        self._proxy_host = self._make_input(20, frame.size.height - 100, host_w, 28, cur_host, "host (e.g. 127.0.0.1)")
        v.addSubview_(self._proxy_host)
        self._proxy_port = self._make_input(20 + host_w + 4, frame.size.height - 100, 60, 28, cur_port, "port")
        v.addSubview_(self._proxy_port)
        # 状态行
        self._status_label = self._make_label(self._proxy_status_text(), 20, frame.size.height - 128, frame.size.width - 40, 11, GREEN, mono=True, bold=False)
        v.addSubview_(self._status_label)
        # 同步可见性
        self._update_proxy_fields_visibility()

        # ─── show_bookmarks 开关 ───
        self._cur_show_bm = bool(self._p.get("show_bookmarks", False))
        bm_y = frame.size.height - 175
        v.addSubview_(self._make_label(
            "homepage", 20, bm_y + 22, 100, 10, LABEL_4
        ))
        # 自定义复选按钮
        self._bm_btn = NSButton.alloc().initWithFrame_(NSMakeRect(20, bm_y - 14, 280, 30))
        self._bm_btn.setBordered_(False)
        self._bm_btn.setWantsLayer_(True)
        self._bm_btn.layer().setCornerRadius_(5)
        self._bm_btn.setAlignment_(0)  # left
        self._bm_btn.setTarget_(self); self._bm_btn.setAction_("toggleShowBookmarks:")
        v.addSubview_(self._bm_btn)
        self._refresh_bm_btn()
        return v

    def _refresh_bm_btn(self):
        from AppKit import NSAttributedString
        on = bool(self._cur_show_bm)
        text = ("☑  首页显示 Chrome 书签" if on else "☐  首页显示 Chrome 书签")
        color = GREEN if on else LABEL_3
        try:
            self._bm_btn.layer().setBackgroundColor_(
                (GREEN_BG if on else _c(255,255,255,0.04)).CGColor()
            )
            self._bm_btn.layer().setBorderWidth_(1 if on else 0.5)
            self._bm_btn.layer().setBorderColor_((GREEN if on else HAIR_2).CGColor())
        except Exception:
            pass
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_(
                "  " + text, _centered(color, NSFont.systemFontOfSize_(12)))
            # 用 left aligned attributed
            from AppKit import NSMutableParagraphStyle
            ps = NSMutableParagraphStyle.alloc().init()
            ps.setAlignment_(0)
            ats = NSAttributedString.alloc().initWithString_attributes_(
                "   " + text, {"NSColor": color, "NSFont": NSFont.systemFontOfSize_(12), "NSParagraphStyle": ps}
            )
            self._bm_btn.setAttributedTitle_(ats)
        except Exception:
            self._bm_btn.setTitle_(text)

    def _proxy_status_text(self):
        if self._cur_proxy in ("socks5", "http"):
            return f"● 走 {self._cur_proxy.upper()} 代理 (绕开系统 VPN)"
        if self._cur_proxy == "system":
            return "● 跟随 macOS 系统代理设置"
        return "● 直连，走系统默认路由"

    def _build_footer(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_FOOT.CGColor())
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, frame.size.height - 0.5, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)

        # 删除（左）
        del_btn = NSButton.alloc().initWithFrame_(NSMakeRect(20, 14, 90, 28))
        del_btn.setTitle_("🗑 DELETE")
        del_btn.setBordered_(False)
        del_btn.setAlignment_(2)
        try: del_btn.cell().setAlignment_(2)
        except Exception: pass
        del_btn.setFont_(NSFont.fontWithName_size_("SF Mono Bold", 10) or NSFont.boldSystemFontOfSize_(10))
        del_btn.setWantsLayer_(True)
        del_btn.layer().setCornerRadius_(5)
        del_btn.layer().setBackgroundColor_(RED_BG.CGColor())
        del_btn.layer().setBorderWidth_(0.5)
        del_btn.layer().setBorderColor_(RED.CGColor())
        from AppKit import NSAttributedString
        mono10 = NSFont.fontWithName_size_("SF Mono Bold", 10) or NSFont.boldSystemFontOfSize_(10)
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_(
                "🗑 DELETE", _centered(RED, mono10))
            del_btn.setAttributedTitle_(ats)
        except Exception:
            pass
        del_btn.setTarget_(self); del_btn.setAction_("doDelete:")
        v.addSubview_(del_btn)

        # 取消
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(frame.size.width - 168, 14, 64, 28))
        cancel_btn.setTitle_("CANCEL")
        cancel_btn.setBordered_(False)
        cancel_btn.setAlignment_(2)
        try: cancel_btn.cell().setAlignment_(2)
        except Exception: pass
        cancel_btn.setFont_(mono10)
        cancel_btn.setWantsLayer_(True); cancel_btn.layer().setCornerRadius_(5)
        cancel_btn.layer().setBackgroundColor_(_c(255,255,255,0.06).CGColor())
        cancel_btn.layer().setBorderWidth_(0.5)
        cancel_btn.layer().setBorderColor_(HAIR_2.CGColor())
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_(
                "CANCEL", _centered(LABEL_3, mono10))
            cancel_btn.setAttributedTitle_(ats)
        except Exception:
            pass
        cancel_btn.setTarget_(self); cancel_btn.setAction_("doCancel:")
        v.addSubview_(cancel_btn)

        # 保存
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(frame.size.width - 100, 14, 80, 28))
        save_btn.setTitle_("SAVE ↵")
        save_btn.setBordered_(False)
        save_btn.setAlignment_(2)
        try: save_btn.cell().setAlignment_(2)
        except Exception: pass
        save_btn.setFont_(mono10)
        save_btn.setWantsLayer_(True); save_btn.layer().setCornerRadius_(5)
        save_btn.layer().setBackgroundColor_(GREEN.CGColor())
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_(
                "SAVE ↵", _centered(_c(14, 14, 16), mono10))
            save_btn.setAttributedTitle_(ats)
        except Exception:
            pass
        save_btn.setTarget_(self); save_btn.setAction_("doSave:")
        v.addSubview_(save_btn)

        return v

    # ── 样式辅助 ─────────────────────────
    def _style_emoji_btn(self, btn, active):
        if active:
            btn.layer().setBackgroundColor_(GREEN_BG.CGColor())
            btn.layer().setBorderWidth_(1)
            btn.layer().setBorderColor_(GREEN.CGColor())
        else:
            btn.layer().setBackgroundColor_(_c(255,255,255,0.04).CGColor())
            btn.layer().setBorderWidth_(0)
        btn.layer().setCornerRadius_(5)

    def _style_seg_btn(self, btn, active):
        if active:
            btn.layer().setBackgroundColor_(_c(255,255,255,0.12).CGColor())
            btn.layer().setBorderWidth_(0)
        else:
            btn.layer().setBackgroundColor_(_c(255,255,255,0.04).CGColor())
            btn.layer().setBorderWidth_(0)
        btn.layer().setCornerRadius_(5)
        from AppKit import NSAttributedString
        try:
            color = LABEL if active else LABEL_3
            ats = NSAttributedString.alloc().initWithString_attributes_(btn.title(), {
                "NSColor": color,
                "NSFont": NSFont.systemFontOfSize_(12),
            })
            btn.setAttributedTitle_(ats)
        except Exception:
            pass

    def _style_proxy_btn(self, btn, active):
        from AppKit import NSAttributedString
        if active:
            btn.layer().setBackgroundColor_(GREEN_BG.CGColor())
            btn.layer().setBorderWidth_(1)
            btn.layer().setBorderColor_(GREEN.CGColor())
            color = GREEN
        else:
            btn.layer().setBackgroundColor_(_c(255,255,255,0.04).CGColor())
            btn.layer().setBorderWidth_(0.5)
            btn.layer().setBorderColor_(HAIR_2.CGColor())
            color = LABEL_3
        btn.layer().setCornerRadius_(5)
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_(btn.title(), {
                "NSColor": color,
                "NSFont": NSFont.fontWithName_size_("SF Mono Bold", 11) or NSFont.boldSystemFontOfSize_(11),
            })
            btn.setAttributedTitle_(ats)
        except Exception:
            pass

    def _update_proxy_fields_visibility(self):
        """根据 proxy 类型 启用/禁用 host/port 输入"""
        enabled = self._cur_proxy in ("socks5", "http")
        self._proxy_host.setEnabled_(enabled)
        self._proxy_port.setEnabled_(enabled)
        if enabled:
            self._proxy_host.layer().setBorderColor_(HAIR_2.CGColor())
            self._proxy_port.layer().setBorderColor_(HAIR_2.CGColor())
            self._proxy_host.setTextColor_(LABEL)
            self._proxy_port.setTextColor_(LABEL)
        else:
            self._proxy_host.layer().setBorderColor_(_c(255,255,255,0.04).CGColor())
            self._proxy_port.layer().setBorderColor_(_c(255,255,255,0.04).CGColor())
            self._proxy_host.setTextColor_(LABEL_4)
            self._proxy_port.setTextColor_(LABEL_4)
        # 状态文字
        if hasattr(self, "_status_label") and self._status_label is not None:
            self._status_label.setStringValue_(self._proxy_status_text())

    # ── Actions ─────────────────────────
    @objc.IBAction
    def pickEmoji_(self, sender):
        idx = int(sender.tag())
        if 0 <= idx < len(EMOJI_OPTIONS):
            self._cur_emoji = EMOJI_OPTIONS[idx]
        # 更新所有 emoji 按钮样式
        for em, btn in self._emoji_btns.items():
            self._style_emoji_btn(btn, em == self._cur_emoji)

    @objc.IBAction
    def pickColor_(self, sender):
        idx = int(sender.tag())
        if 0 <= idx < len(COLOR_OPTIONS):
            self._cur_color = COLOR_OPTIONS[idx][0]
        for name, (chip, _ovr) in self._color_btns.items():
            if name == self._cur_color:
                chip.layer().setBorderWidth_(2)
                chip.layer().setBorderColor_(LABEL.CGColor())
            else:
                chip.layer().setBorderWidth_(0)

    @objc.IBAction
    def pickMode_(self, sender):
        self._cur_mode = "work" if int(sender.tag()) == 0 else "slack"
        for name, btn in self._mode_btns.items():
            self._style_seg_btn(btn, name == self._cur_mode)

    @objc.IBAction
    def toggleShowBookmarks_(self, sender):
        self._cur_show_bm = not getattr(self, "_cur_show_bm", False)
        self._refresh_bm_btn()

    @objc.IBAction
    def pickTheme_(self, sender):
        themes = ["red", "green", "yellow"]
        idx = int(sender.tag())
        if 0 <= idx < len(themes):
            self._cur_theme = themes[idx]
        for name, (chip, _) in self._theme_btns.items():
            if name == self._cur_theme:
                chip.layer().setBorderWidth_(2.5)
                chip.layer().setBorderColor_(LABEL.CGColor())
            else:
                chip.layer().setBorderWidth_(0)

    @objc.IBAction
    def pickProxyType_(self, sender):
        idx = int(sender.tag())
        if 0 <= idx < len(PROXY_TYPES):
            self._cur_proxy = PROXY_TYPES[idx].lower()
        for name, btn in self._proxy_btns.items():
            self._style_proxy_btn(btn, name == self._cur_proxy)
        self._update_proxy_fields_visibility()

    @objc.IBAction
    def doSave_(self, sender):
        # 提取并校验
        self._p["name"] = (self._name_input.stringValue() or "未命名").strip()
        self._p["note"] = self._note_input.stringValue().strip()
        self._p["emoji"] = self._cur_emoji
        self._p["color"] = self._cur_color
        self._p["mode"]  = self._cur_mode
        self._p["theme"] = self._cur_theme
        self._p["show_bookmarks"] = bool(getattr(self, "_cur_show_bm", False))
        if self._cur_proxy in ("socks5", "http"):
            host = self._proxy_host.stringValue().strip()
            try:
                port = int(self._proxy_port.stringValue().strip())
            except ValueError:
                port = 0
            if not host or port <= 0:
                a = NSAlert.alloc().init()
                a.setMessageText_("代理参数缺失")
                a.setInformativeText_("选了 SOCKS5 / HTTP 必须填主机和端口")
                a.runModal()
                return
            self._p["proxy"] = {"type": self._cur_proxy, "host": host, "port": port}
        elif self._cur_proxy == "system":
            self._p["proxy"] = {"type": "system"}
        else:
            self._p["proxy"] = {"type": "direct"}
        # 回调
        try:
            self._on_save(self._p)
        except Exception as e:
            NSLog(f"editWindow on_save err: {e}")
        self._window.orderOut_(None)

    @objc.IBAction
    def doCancel_(self, sender):
        self._window.orderOut_(None)

    @objc.IBAction
    def doDelete_(self, sender):
        a = NSAlert.alloc().init()
        a.setMessageText_(f"删除工作区 \"{self._p.get('name', '')}\" ？")
        a.setInformativeText_("删除后不可恢复")
        a.addButtonWithTitle_("删除")
        a.addButtonWithTitle_("取消")
        if a.runModal() != NSAlertFirstButtonReturn:
            return
        try:
            self._on_delete(self._p)
        except Exception as e:
            NSLog(f"editWindow on_delete err: {e}")
        self._window.orderOut_(None)
