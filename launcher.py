"""
Meowser — 启动器（L Linear/Raycast 暗色风）
"""

import objc
from AppKit import (
    NSWindow, NSView, NSTextField, NSColor, NSFont, NSButton,
    NSScrollView, NSImage,
    NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSWindowStyleMaskFullSizeContentView,
    NSBackingStoreBuffered, NSScreen, NSAppearance,
    NSAlert, NSAlertFirstButtonReturn, NSAttributedString,
    NSWindowTitleHidden,
)
from Foundation import NSObject, NSLog, NSMakeRect, NSMakeSize

from profiles import (
    load_profiles, save_profiles, make_blank, upsert, delete, find_by_id,
)
from edit_window import EditWindowController, _GradientView, COLOR_OPTIONS


def _c(r, g, b, a=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(r/255.0, g/255.0, b/255.0, a)


# ── 配色（与 edit_window 同一套）──
BG_WIN     = _c(22, 22, 24)
BG_HEAD    = _c(28, 28, 30)
BG_LIST    = _c(14, 14, 16)
BG_TIP     = _c(255, 149, 0, 0.06)
BG_FOOT    = _c(14, 14, 16)
HAIR       = _c(255, 255, 255, 0.06)
HAIR_2     = _c(255, 255, 255, 0.10)
LABEL      = _c(255, 255, 255)
LABEL_2    = _c(255, 255, 255, 0.85)
LABEL_3    = _c(255, 255, 255, 0.50)
LABEL_4    = _c(255, 255, 255, 0.35)
GREEN      = _c(74, 222, 128)
GREEN_BG   = _c(74, 222, 128, 0.10)
PINK       = _c(236, 72, 153)
PINK_BG    = _c(236, 72, 153, 0.10)
BLUE       = _c(93, 173, 226)
BLUE_BG    = _c(93, 173, 226, 0.10)
YELLOW     = _c(255, 214, 10)


COLOR_MAP = {name: pair for name, pair in COLOR_OPTIONS}


def _mono(size, bold=True):
    if bold:
        return NSFont.fontWithName_size_("SF Mono Bold", size) or NSFont.boldSystemFontOfSize_(size)
    return NSFont.fontWithName_size_("SF Mono", size) or NSFont.systemFontOfSize_(size)


def _centered_attrs(color, font):
    """生成带居中段落样式的属性字典（NSButton 的 attributedTitle 用）"""
    from AppKit import NSMutableParagraphStyle
    ps = NSMutableParagraphStyle.alloc().init()
    ps.setAlignment_(2)  # NSTextAlignmentCenter
    return {"NSColor": color, "NSFont": font, "NSParagraphStyle": ps}


# Theme 色（红 / 绿 / 黄 + 兜底蓝）
THEME_COLORS = {
    "red":    _c(255, 59, 48),
    "green":  _c(52, 199, 89),
    "yellow": _c(255, 204, 0),
    "blue":   _c(10, 132, 255),
}
THEME_LIGHT = {  # 浅色背景，用于 webview 周边
    "red":    _c(255, 59, 48,  0.10),
    "green":  _c(52, 199, 89,  0.10),
    "yellow": _c(255, 204, 0,  0.14),
    "blue":   _c(10, 132, 255, 0.10),
}


def theme_for(profile):
    """profile 没设 theme 时按 mode 推断"""
    t = (profile or {}).get("theme")
    if t in THEME_COLORS:
        return t
    name = (profile or {}).get("name", "")
    # 默认推断：默认=黄, 工作=绿, 娱乐=红
    if name in ("工作",): return "green"
    if name in ("娱乐",): return "red"
    return "yellow"


class LauncherController(NSObject):
    """L 暗色启动器"""

    WIDTH = 720

    def initWithApp_(self, app_delegate):
        self = objc.super(LauncherController, self).init()
        if self is None:
            return None
        self._app = app_delegate
        self._window = None
        self._list_view = None
        self._scroll_view = None
        self._edit_ctrl = None
        return self

    def show(self):
        if self._window is None:
            self._build()
        else:
            self._populate()
        # 多屏环境：找到 origin=(0,0) 的真主屏，手动居中
        try:
            from AppKit import NSScreen as _S
            target = None
            for s in _S.screens():
                f = s.frame()
                if f.origin.x == 0 and f.origin.y == 0:
                    target = s; break
            if target is None:
                target = _S.mainScreen()
            sf = target.visibleFrame()
            wf = self._window.frame()
            cx = sf.origin.x + (sf.size.width - wf.size.width) / 2
            cy = sf.origin.y + (sf.size.height - wf.size.height) / 2
            self._window.setFrameOrigin_((cx, cy))
        except Exception:
            pass
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        app = NSApplication.sharedApplication()
        # ★ 关键：把 activation policy 临时升到 Regular，否则 LSUIElement app 抢不了焦点
        try:
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception:
            pass
        app.activateIgnoringOtherApps_(True)
        self._window.setLevel_(3)  # Floating level
        self._window.makeKeyAndOrderFront_(None)
        self._window.orderFrontRegardless()
        try:
            from Foundation import NSLog
            f = self._window.frame()
            NSLog(f"📋 启动器已显示: pos=({f.origin.x:.0f}, {f.origin.y:.0f}) size=({f.size.width:.0f}x{f.size.height:.0f}) visible={self._window.isVisible()}")
        except Exception:
            pass

    def _build(self):
        H_TITLEBAR = 38
        H_HEADER = 56
        H_LIST_HEAD = 28
        H_LIST = 320          # 滚动区
        H_TIP = 64
        H_FOOTER = 36
        total_h = H_TITLEBAR + H_HEADER + H_LIST_HEAD + H_LIST + H_TIP + H_FOOTER

        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, self.WIDTH, total_h),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskFullSizeContentView,
            NSBackingStoreBuffered, False,
        )
        win.setTitle_("Meowser")
        win.setTitlebarAppearsTransparent_(True)
        win.setTitleVisibility_(NSWindowTitleHidden)
        win.setMovableByWindowBackground_(True)
        try:
            win.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        except Exception:
            pass
        win.setBackgroundColor_(BG_WIN)
        # 关键：跨所有 Space + 跟随用户当前 Space（无论 AS 是不是 fullscreen 都能看到）
        try:
            from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorFullScreenAuxiliary
            win.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces |
                NSWindowCollectionBehaviorFullScreenAuxiliary
            )
        except Exception:
            try:
                win.setCollectionBehavior_(1 | (1 << 8))  # CanJoinAllSpaces | FullScreenAuxiliary
            except Exception:
                pass

        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.WIDTH, total_h))
        content.setWantsLayer_(True)
        content.layer().setBackgroundColor_(BG_WIN.CGColor())
        win.setContentView_(content)

        # 自顶向下
        y = total_h

        # 顶部命令栏占位（titlebar 区域）
        y -= H_TITLEBAR
        cmd_bar = self._build_cmdbar(NSMakeRect(0, y, self.WIDTH, H_TITLEBAR))
        content.addSubview_(cmd_bar)

        # Header
        y -= H_HEADER
        header = self._build_header(NSMakeRect(0, y, self.WIDTH, H_HEADER))
        content.addSubview_(header)

        # 列表表头
        y -= H_LIST_HEAD
        list_head = self._build_list_head(NSMakeRect(0, y, self.WIDTH, H_LIST_HEAD))
        content.addSubview_(list_head)

        # 列表（滚动）
        y -= H_LIST
        sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, y, self.WIDTH, H_LIST))
        sv.setHasVerticalScroller_(True)
        sv.setBorderType_(0)
        sv.setBackgroundColor_(BG_LIST)
        sv.setDrawsBackground_(True)
        list_view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.WIDTH, 100))
        list_view.setWantsLayer_(True)
        list_view.layer().setBackgroundColor_(BG_LIST.CGColor())
        sv.setDocumentView_(list_view)
        content.addSubview_(sv)
        self._list_view = list_view
        self._scroll_view = sv

        # Cookie tip strip
        y -= H_TIP
        tip = self._build_tip(NSMakeRect(0, y, self.WIDTH, H_TIP))
        content.addSubview_(tip)

        # Footer
        y -= H_FOOTER
        foot = self._build_footer(NSMakeRect(0, y, self.WIDTH, H_FOOTER))
        content.addSubview_(foot)

        self._window = win
        self._populate()

    # ── 各区域构造 ─────────────────────
    def _build_cmdbar(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_HEAD.CGColor())
        # 命令栏（伪命令栏，仅作视觉）
        cmd = NSView.alloc().initWithFrame_(NSMakeRect(80, 7, frame.size.width - 240, 24))
        cmd.setWantsLayer_(True)
        cmd.layer().setBackgroundColor_(_c(255,255,255,0.06).CGColor())
        cmd.layer().setCornerRadius_(5)
        cmd.layer().setBorderWidth_(0.5)
        cmd.layer().setBorderColor_(HAIR_2.CGColor())
        ico = NSTextField.alloc().initWithFrame_(NSMakeRect(8, 4, 16, 16))
        ico.setBezeled_(False); ico.setDrawsBackground_(False)
        ico.setEditable_(False); ico.setSelectable_(False)
        ico.setStringValue_("🔍")
        ico.setFont_(NSFont.systemFontOfSize_(11))
        cmd.addSubview_(ico)
        ph = NSTextField.alloc().initWithFrame_(NSMakeRect(28, 4, 200, 16))
        ph.setBezeled_(False); ph.setDrawsBackground_(False)
        ph.setEditable_(False); ph.setSelectable_(False)
        ph.setStringValue_("搜索工作区...")
        ph.setFont_(_mono(11, bold=False))
        ph.setTextColor_(LABEL_4)
        cmd.addSubview_(ph)
        # ⌘K hint
        kbd = NSTextField.alloc().initWithFrame_(NSMakeRect(cmd.frame().size.width - 38, 4, 32, 16))
        kbd.setBezeled_(False); kbd.setDrawsBackground_(True)
        kbd.setBackgroundColor_(_c(255,255,255,0.06))
        kbd.setEditable_(False); kbd.setSelectable_(False)
        kbd.setStringValue_("⌘K")
        kbd.setFont_(_mono(9))
        kbd.setTextColor_(LABEL_3); kbd.setAlignment_(2)
        kbd.setWantsLayer_(True); kbd.layer().setCornerRadius_(3)
        cmd.addSubview_(kbd)
        v.addSubview_(cmd)
        # 底部分隔线
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)
        return v

    def _build_header(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_HEAD.CGColor())

        # 左：● WORKSPACES (n)
        dot = NSTextField.alloc().initWithFrame_(NSMakeRect(20, frame.size.height - 30, 14, 14))
        dot.setBezeled_(False); dot.setDrawsBackground_(False)
        dot.setEditable_(False); dot.setSelectable_(False)
        dot.setStringValue_("●")
        dot.setFont_(NSFont.systemFontOfSize_(11))
        dot.setTextColor_(GREEN)
        v.addSubview_(dot)

        title = NSTextField.alloc().initWithFrame_(NSMakeRect(36, frame.size.height - 32, 200, 20))
        title.setBezeled_(False); title.setDrawsBackground_(False)
        title.setEditable_(False); title.setSelectable_(False)
        title.setStringValue_("WORKSPACES")
        title.setFont_(_mono(13))
        title.setTextColor_(LABEL_2)
        v.addSubview_(title)

        # count
        count_n = len(load_profiles())
        cnt = NSTextField.alloc().initWithFrame_(NSMakeRect(140, frame.size.height - 30, 30, 16))
        cnt.setBezeled_(False); cnt.setDrawsBackground_(True)
        cnt.setBackgroundColor_(_c(255,255,255,0.06))
        cnt.setEditable_(False); cnt.setSelectable_(False)
        cnt.setStringValue_(f" {count_n} ")
        cnt.setFont_(_mono(10))
        cnt.setTextColor_(LABEL_3); cnt.setAlignment_(2)
        cnt.setWantsLayer_(True); cnt.layer().setCornerRadius_(3)
        v.addSubview_(cnt)

        # 副标题
        sub = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 8, 400, 16))
        sub.setBezeled_(False); sub.setDrawsBackground_(False)
        sub.setEditable_(False); sub.setSelectable_(False)
        sub.setStringValue_("每个工作区独立 Cookie / 缓存 / 代理 · 数据本地存储")
        sub.setFont_(NSFont.systemFontOfSize_(11))
        sub.setTextColor_(LABEL_3)
        v.addSubview_(sub)

        # 右：动作按钮
        new_btn = self._make_pill_btn("＋ 新建", frame.size.width - 100, frame.size.height - 32, 80, primary=True)
        new_btn.setTarget_(self); new_btn.setAction_("addProfile:")
        v.addSubview_(new_btn)

        # 底部分隔线
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)
        return v

    def _make_pill_btn(self, title, x, y, w, primary=False):
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, w, 24))
        btn.setTitle_(title)
        btn.setBordered_(False)
        btn.setAlignment_(2)
        # 关键：cell 也要 setAlignment（borderless 按钮真正生效的地方）
        try:
            btn.cell().setAlignment_(2)
        except Exception:
            pass
        btn.setWantsLayer_(True)
        btn.layer().setCornerRadius_(5)
        if primary:
            btn.layer().setBackgroundColor_(GREEN_BG.CGColor())
            btn.layer().setBorderWidth_(0.5)
            btn.layer().setBorderColor_(GREEN.CGColor())
            color = GREEN
        else:
            btn.layer().setBackgroundColor_(_c(255,255,255,0.06).CGColor())
            btn.layer().setBorderWidth_(0.5)
            btn.layer().setBorderColor_(HAIR_2.CGColor())
            color = LABEL_2
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_(title,
                _centered_attrs(color, _mono(11)))
            btn.setAttributedTitle_(ats)
        except Exception:
            pass
        return btn

    def _build_list_head(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_LIST.CGColor())

        # 严格对齐 _build_row 的列计算
        W = frame.size.width
        TH_W = 4; EM_W = 28; MODE_W = 60; PROXY_W = 180; GEAR_W = 32; RUN_W = 60
        right_margin = 12
        run_x   = W - right_margin - RUN_W
        gear_x  = run_x - 8 - GEAR_W
        proxy_x = gear_x - 8 - PROXY_W
        mode_x  = proxy_x - 8 - MODE_W
        # 中间 name+note 起点（与行一致）
        name_x  = 12 + TH_W + 8 + EM_W + 12

        labels = [
            (name_x, "NAME / NOTE", name_x + 200),
            (mode_x, "MODE",        MODE_W),
            (proxy_x, "PROXY",      PROXY_W),
        ]
        for x, text, w in labels:
            l = NSTextField.alloc().initWithFrame_(NSMakeRect(x, frame.size.height - 20, w, 14))
            l.setBezeled_(False); l.setDrawsBackground_(False)
            l.setEditable_(False); l.setSelectable_(False)
            l.setStringValue_(text)
            l.setFont_(_mono(9))
            l.setTextColor_(LABEL_4)
            # MODE / PROXY 表头跟列内容居中对齐
            if text in ("MODE", "PROXY"):
                l.setAlignment_(2)
            v.addSubview_(l)
        # 底部分隔线
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(HAIR.CGColor())
        v.addSubview_(sep)
        return v

    def _build_tip(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_TIP.CGColor())
        # 顶部分隔线
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, frame.size.height - 0.5, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(_c(255, 149, 0, 0.20).CGColor())
        v.addSubview_(sep)

        # 图标
        ico = _GradientView.alloc().initWithFrame_colors_emoji_(
            NSMakeRect(20, (frame.size.height - 32) / 2, 32, 32),
            [_c(255, 149, 0), _c(255, 59, 48)],
            "🍪",
        )
        v.addSubview_(ico)

        # 文字
        title = NSTextField.alloc().initWithFrame_(NSMakeRect(64, frame.size.height - 28, 400, 16))
        title.setBezeled_(False); title.setDrawsBackground_(False)
        title.setEditable_(False); title.setSelectable_(False)
        title.setStringValue_("Google 不让登？")
        title.setFont_(NSFont.boldSystemFontOfSize_(12))
        title.setTextColor_(YELLOW)
        v.addSubview_(title)
        sub = NSTextField.alloc().initWithFrame_(NSMakeRect(64, 12, 500, 14))
        sub.setBezeled_(False); sub.setDrawsBackground_(False)
        sub.setEditable_(False); sub.setSelectable_(False)
        sub.setStringValue_('一键从 Safari 同步 Cookie · 永久解决（需要「完全磁盘访问」权限）')
        sub.setFont_(NSFont.systemFontOfSize_(11))
        sub.setTextColor_(LABEL_3)
        v.addSubview_(sub)

        # 同步按钮
        btn = self._make_pill_btn("SYNC →", frame.size.width - 90, (frame.size.height - 28) / 2, 70, primary=True)
        btn.setTarget_(self); btn.setAction_("syncCookies:")
        v.addSubview_(btn)
        return v

    def _build_footer(self, frame):
        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_FOOT.CGColor())

        l = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 10, 400, 14))
        l.setBezeled_(False); l.setDrawsBackground_(False)
        l.setEditable_(False); l.setSelectable_(False)
        l.setStringValue_("📂 ~/.meowser/profiles.json")
        l.setFont_(_mono(10))
        l.setTextColor_(LABEL_4)
        v.addSubview_(l)

        r = NSTextField.alloc().initWithFrame_(NSMakeRect(frame.size.width - 280, 10, 260, 14))
        r.setBezeled_(False); r.setDrawsBackground_(False)
        r.setEditable_(False); r.setSelectable_(False)
        r.setStringValue_("v1.6.0 · 本地存储 · 0 上传")
        r.setFont_(_mono(10))
        r.setTextColor_(LABEL_4); r.setAlignment_(2)
        v.addSubview_(r)
        return v

    # ── 渲染 profile 列表 ─────────────────
    def _populate(self):
        for sv in list(self._list_view.subviews()):
            sv.removeFromSuperview()
        profiles = load_profiles()
        row_h = 56
        n = len(profiles)
        total_h = max(self._scroll_view.frame().size.height, n * row_h + 8)
        self._list_view.setFrame_(NSMakeRect(0, 0, self.WIDTH, total_h))

        y = total_h
        for p in profiles:
            y -= row_h
            self._list_view.addSubview_(self._build_row(p, NSMakeRect(0, y, self.WIDTH, row_h)))

    def _build_row(self, p, frame):
        # ─── 列宽规划（W=720 时严格不重叠）───
        # | theme | emoji |   name+note   | mode | proxy | gear | run |
        #   12+8    28+12       变长       60+8   200+8   32+8  60+12
        W = frame.size.width
        H = frame.size.height
        x = 12
        TH_W = 4         # 左边主题色条
        EM_W = 28        # emoji 头像
        MODE_W = 60
        PROXY_W = 180
        GEAR_W = 32
        RUN_W = 60
        right_margin = 12

        v = NSView.alloc().initWithFrame_(frame)
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(BG_LIST.CGColor())

        # ─ 主题色竖条 ─
        theme = theme_for(p)
        th_color = THEME_COLORS.get(theme, THEME_COLORS["yellow"])
        th = NSView.alloc().initWithFrame_(NSMakeRect(x, (H - 30) / 2, TH_W, 30))
        th.setWantsLayer_(True)
        th.layer().setBackgroundColor_(th_color.CGColor())
        th.layer().setCornerRadius_(2)
        v.addSubview_(th)
        x += TH_W + 8

        # ─ emoji ─
        emoji = p.get("emoji", "🐱")
        em = NSTextField.alloc().initWithFrame_(NSMakeRect(x, (H - 28) / 2, EM_W, 28))
        em.setBezeled_(False); em.setDrawsBackground_(True)
        em.setBackgroundColor_(_c(255,255,255,0.04))
        em.setEditable_(False); em.setSelectable_(False)
        em.setStringValue_(emoji); em.setAlignment_(2)
        em.setFont_(NSFont.systemFontOfSize_(16))
        em.setWantsLayer_(True); em.layer().setCornerRadius_(5)
        v.addSubview_(em)
        x += EM_W + 12

        # ─ 右侧固定区先算 ─
        run_x   = W - right_margin - RUN_W
        gear_x  = run_x - 8 - GEAR_W
        proxy_x = gear_x - 8 - PROXY_W
        mode_x  = proxy_x - 8 - MODE_W

        # 中段 name+note 自适应
        name_x = x
        name_w = mode_x - x - 8
        if name_w < 80:
            name_w = 80

        # ─ name + note ─
        name = p.get("name", "(未命名)")
        n_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(name_x, H - 28, name_w, 18))
        n_lbl.setBezeled_(False); n_lbl.setDrawsBackground_(False)
        n_lbl.setEditable_(False); n_lbl.setSelectable_(False)
        n_lbl.setStringValue_(name)
        n_lbl.setFont_(NSFont.boldSystemFontOfSize_(13))
        n_lbl.setTextColor_(LABEL)
        n_lbl.setLineBreakMode_(4)  # NSLineBreakByTruncatingTail
        v.addSubview_(n_lbl)

        note = p.get("note", "")
        no_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(name_x, 8, name_w, 16))
        no_lbl.setBezeled_(False); no_lbl.setDrawsBackground_(False)
        no_lbl.setEditable_(False); no_lbl.setSelectable_(False)
        no_lbl.setStringValue_(note)
        no_lbl.setFont_(NSFont.systemFontOfSize_(11))
        no_lbl.setTextColor_(LABEL_3)
        no_lbl.setLineBreakMode_(4)
        v.addSubview_(no_lbl)

        # ─ mode badge ─
        mode = p.get("mode", "work")
        mode_text = "work" if mode == "work" else "slack"
        mode_color = BLUE if mode == "work" else PINK
        mode_bg = BLUE_BG if mode == "work" else PINK_BG
        mb = NSTextField.alloc().initWithFrame_(NSMakeRect(mode_x, (H - 20) / 2, MODE_W, 20))
        mb.setBezeled_(False); mb.setDrawsBackground_(True)
        mb.setBackgroundColor_(mode_bg)
        mb.setEditable_(False); mb.setSelectable_(False)
        mb.setStringValue_(mode_text); mb.setAlignment_(2)
        mb.setFont_(_mono(10))
        mb.setTextColor_(mode_color)
        mb.setWantsLayer_(True); mb.layer().setCornerRadius_(10)
        v.addSubview_(mb)

        # ─ proxy ─
        proxy = p.get("proxy", {"type": "direct"})
        if proxy.get("type") == "socks5":
            ptxt = f"socks5 {proxy.get('host', '')}:{proxy.get('port', '')}"
            pcol = GREEN
        elif proxy.get("type") == "http":
            ptxt = f"http {proxy.get('host', '')}:{proxy.get('port', '')}"
            pcol = GREEN
        elif proxy.get("type") == "system":
            ptxt = "system"
            pcol = LABEL_3
        else:
            ptxt = "DIRECT"
            pcol = LABEL_4
        pp = NSTextField.alloc().initWithFrame_(NSMakeRect(proxy_x, (H - 18) / 2, PROXY_W, 18))
        pp.setBezeled_(False); pp.setDrawsBackground_(False)
        pp.setEditable_(False); pp.setSelectable_(False)
        pp.setStringValue_(ptxt)
        pp.setFont_(_mono(10))
        pp.setTextColor_(pcol)
        pp.setLineBreakMode_(4)
        v.addSubview_(pp)

        # ─ edit (gear) ─
        edit = NSButton.alloc().initWithFrame_(NSMakeRect(gear_x, (H - 26) / 2, GEAR_W, 26))
        edit.setBordered_(False)
        edit.setWantsLayer_(True)
        edit.layer().setCornerRadius_(5)
        edit.layer().setBackgroundColor_(_c(255,255,255,0.06).CGColor())
        edit.layer().setBorderWidth_(0.5)
        edit.layer().setBorderColor_(HAIR_2.CGColor())
        edit.setAlignment_(2)
        try: edit.cell().setAlignment_(2)
        except Exception: pass
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_("⚙",
                _centered_attrs(LABEL_3, NSFont.systemFontOfSize_(13)))
            edit.setAttributedTitle_(ats)
        except Exception:
            edit.setTitle_("⚙")
        edit.setTarget_(self); edit.setAction_("editProfile:")
        edit.setTag_(self._tag_for_id(p.get("id", "")))
        v.addSubview_(edit)

        # ─ run button ─
        run = NSButton.alloc().initWithFrame_(NSMakeRect(run_x, (H - 26) / 2, RUN_W, 26))
        run.setBordered_(False)
        run.setWantsLayer_(True)
        run.layer().setCornerRadius_(5)
        run.layer().setBackgroundColor_(GREEN.CGColor())
        run.setAlignment_(2)
        try: run.cell().setAlignment_(2)
        except Exception: pass
        try:
            ats = NSAttributedString.alloc().initWithString_attributes_("▶ RUN",
                _centered_attrs(_c(14, 14, 16), _mono(10)))
            run.setAttributedTitle_(ats)
        except Exception:
            run.setTitle_("▶ RUN")
        run.setTarget_(self); run.setAction_("launchProfile:")
        run.setTag_(self._tag_for_id(p.get("id", "")))
        v.addSubview_(run)

        # 底部分隔线
        sep = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, 0.5))
        sep.setWantsLayer_(True); sep.layer().setBackgroundColor_(_c(255,255,255,0.04).CGColor())
        v.addSubview_(sep)

        return v

    # ── id ↔ tag 映射 ───────────────────
    _id_to_tag = {}
    _tag_to_id = {}
    _next_tag = 1000

    def _tag_for_id(self, pid):
        if pid in self._id_to_tag:
            return self._id_to_tag[pid]
        tag = LauncherController._next_tag
        LauncherController._next_tag += 1
        self._id_to_tag[pid] = tag
        self._tag_to_id[tag] = pid
        return tag

    def _id_for_tag(self, tag):
        return self._tag_to_id.get(int(tag))

    # ── Actions ─────────────────────────
    @objc.IBAction
    def launchProfile_(self, sender):
        pid = self._id_for_tag(sender.tag())
        if not pid:
            return
        profiles = load_profiles()
        p = find_by_id(profiles, pid)
        if p is None:
            return
        try:
            self._app.switchToProfile_(p)
        except Exception as e:
            NSLog(f"launchProfile_ err: {e}")
        if self._window is not None:
            self._window.orderOut_(None)
        # 还原 activation policy 到 Accessory（Dock 不显示图标）
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception:
            pass

    @objc.IBAction
    def addProfile_(self, sender):
        np = make_blank()
        self._open_edit(np)

    @objc.IBAction
    def editProfile_(self, sender):
        pid = self._id_for_tag(sender.tag())
        if not pid:
            return
        profiles = load_profiles()
        p = find_by_id(profiles, pid)
        if p is None:
            return
        self._open_edit(p)

    @objc.IBAction
    def syncCookies_(self, sender):
        # 简单提示框（真同步逻辑下一轮做）
        a = NSAlert.alloc().init()
        a.setMessageText_("🍪 Cookie 同步（下一轮上线）")
        a.setInformativeText_(
            '本功能需要「完全磁盘访问」权限以读取 Safari 的 Cookies。\n'
            '实现完成后，从这里点一下，即可把 Safari 的 Google 登录态搬到 Meowser，永久解决登录问题。'
        )
        a.addButtonWithTitle_("好")
        a.runModal()

    def _open_edit(self, p):
        self._edit_ctrl = EditWindowController.alloc().initWithProfile_onSave_onDelete_(
            p, self._on_save_profile, self._on_delete_profile
        )
        self._edit_ctrl.show()

    def _on_save_profile(self, p):
        profiles = load_profiles()
        profiles = upsert(profiles, p)
        save_profiles(profiles)
        self._populate()

    def _on_delete_profile(self, p):
        profiles = load_profiles()
        profiles = delete(profiles, p["id"])
        save_profiles(profiles)
        self._populate()
