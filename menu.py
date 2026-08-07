"""
Meowser — 菜单栏 NSPopover 自定义面板
- Header: Boss 身份卡（头像 + 名字 + 模式 + 窗口数）
- Quick Actions: 显隐 / 新窗 / 整理 / 首页
- 摆放：3x3 方向键盘 + 平铺/叠放分段
- 滑块：窗口间距 + 不透明度
- 行：代理状态 / 置顶 / 无痕
- 二级菜单：小窗尺寸 / 常用网站 / 输入网址
- 设置入口：高级设置（快捷键）
- Footer: 快捷键提示 + 退出
"""

import objc
from AppKit import (
    NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem,
    NSApplication, NSImage, NSAlert, NSTextField, NSMakeRect,
    NSAlertFirstButtonReturn, NSFont, NSColor, NSSlider,
    NSView, NSViewController, NSPopover, NSPopoverBehaviorTransient,
    NSButton, NSStackView, NSLayoutConstraint,
    NSUserInterfaceLayoutOrientationVertical, NSUserInterfaceLayoutOrientationHorizontal,
    NSBezelStyleRounded, NSBezelStyleTexturedRounded,
    NSImageNameStatusAvailable, NSImageNameStatusUnavailable,
)
from Foundation import NSObject, NSLog, NSNumber, NSMakeSize, NSMakePoint, NSBundle, NSRectEdgeMinY


_VALID_MODS = {"cmd", "alt", "opt", "shift", "ctrl"}


def _str_to_hotkey(s):
    parts = [p.strip().lower() for p in s.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return None
    mods = [p for p in parts[:-1] if p in _VALID_MODS]
    key = parts[-1].upper()
    if len(mods) != len(parts) - 1 or not key:
        return None
    return {"modifiers": mods, "key": key}


def _hotkey_to_str(hk):
    parts = list(hk.get("modifiers", [])) + [hk.get("key", "")]
    return "+".join(parts)


# ─── 颜色辅助 ──────────────────────────────
def _color(r, g, b, a=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(r/255.0, g/255.0, b/255.0, a)

C_BLUE   = _color(0, 113, 227)
C_GREEN  = _color(52, 199, 89)
C_ORANGE = _color(255, 149, 0)
C_RED    = _color(255, 59, 48)
C_PURPLE = _color(175, 82, 222)
C_PINK   = _color(255, 45, 85)
C_GRAY   = _color(142, 142, 147)
C_LABEL  = _color(29, 29, 31)
C_LABEL2 = _color(110, 110, 115)
C_LABEL3 = _color(150, 150, 155)
C_FILL1  = _color(0, 0, 0, 0.04)
C_FILL2  = _color(0, 0, 0, 0.08)
C_HAIR   = _color(0, 0, 0, 0.08)
C_BG     = _color(255, 255, 255)
C_BG_SEC = _color(250, 250, 252)


# ─── 自定义彩色图标方块（NSView 加 layer）───
class IconChip(NSView):
    def initWithSize_emoji_color_(self, size, emoji, color):
        self = objc.super(IconChip, self).initWithFrame_(NSMakeRect(0, 0, size, size))
        if self is None:
            return None
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(size * 0.28)
        self.layer().setBackgroundColor_(color.CGColor())
        # 文字
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
        lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
        lbl.setEditable_(False); lbl.setSelectable_(False)
        lbl.setAlignment_(2)  # center
        lbl.setStringValue_(emoji)
        lbl.setFont_(NSFont.systemFontOfSize_(size * 0.55))
        lbl.setTextColor_(NSColor.whiteColor())
        # 垂直居中
        from Foundation import NSMakeRect as MR
        lbl.setFrame_(MR(0, -size * 0.12, size, size))
        self.addSubview_(lbl)
        # 阴影
        from AppKit import NSShadow
        sh = NSShadow.alloc().init()
        sh.setShadowColor_(NSColor.colorWithWhite_alpha_(0, 0.12))
        sh.setShadowOffset_(NSMakeSize(0, -1))
        sh.setShadowBlurRadius_(2)
        self.setShadow_(sh)
        return self


# ─── 整体 popover 视图控制器 ──────────────
class PopoverVC(NSViewController):
    """NSPopover 的内容视图控制器"""

    def initWithStatusBar_(self, status_bar_ctrl):
        self = objc.super(PopoverVC, self).init()
        if self is None:
            return None
        self._sb = status_bar_ctrl
        self._build_view()
        return self

    # popover 容器宽度
    W = 320

    def _build_view(self):
        from AppKit import NSVisualEffectView, NSVisualEffectMaterialPopover, NSVisualEffectStateActive
        # 用 vibrancy 背景，跟随系统暗黑
        root = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, 800))
        try:
            root.setMaterial_(NSVisualEffectMaterialPopover)
            root.setState_(NSVisualEffectStateActive)
            root.setBlendingMode_(0)  # behind window
        except Exception:
            pass
        self._root = root
        self.setView_(root)
        self._refresh()  # 装载子视图

    def _refresh(self):
        """根据当前状态重建内部布局（每次打开都会调）"""
        # 清除旧子视图
        for sv in list(self._root.subviews()):
            sv.removeFromSuperview()

        cur_y = 0  # 从底部往上累加（因为 macOS 坐标系）
        sections = []

        # 准备数据
        cfg = self._sb._app_delegate.config() if self._sb._app_delegate else {}
        profile = cfg.get("profile", {"name": "默认", "mode": "work"})
        layout = cfg.get("layout", {"edge": "left", "style": "tile", "gap": 8})
        proxy = profile.get("proxy", {"type": "direct"})
        small = cfg.get("small_window_size", {"w": 200, "h": 150})
        alpha = getattr(self._sb._window, "_alpha", 1.0)
        pinned = getattr(self._sb._window, "_pinned", True)

        try:
            from boss_manager import get_active_boss
            boss = get_active_boss()
            wn = len(boss.all_windows()) if boss else 1
        except Exception:
            wn = 1

        # 自下而上摆放（计算总高度）
        # 1. Footer
        footer = self._build_footer(cfg)
        # 2. 设置入口
        settings_row = self._build_row(
            "⚙", C_GRAY, "快捷键 & 高级设置...", None,
            arrow=True, action="openAdvanced:")
        # 3. 二级菜单组
        sub_input = self._build_row("🔗", C_GRAY, "输入网址", "⌘L",
            kbd=True, action="openURL:")
        sub_safari = self._build_row("🦁", C_BLUE, "用 Safari 打开当前页",
            "登录 Google 等被拦时使用", arrow=False, action="openInSafari:")
        sub_chrome = self._build_row("🌐", C_GREEN, "用 Chrome 打开当前页",
            "支持 1Password 等扩展（系统 Chrome 全功能）", arrow=False, action="openInChrome:")
        sub_1pass = self._build_row("🔐", C_PURPLE, "1Password 填充 (CLI)",
            "需要 op CLI · 备选方案", arrow=False, action="fill1Password:")
        sub_sites = self._build_row("⭐", C_RED, "常用网站",
            "B站 · YouTube · GitHub · ...", arrow=True, action="openSitesMenu:")
        sub_size  = self._build_row("📐", C_BLUE, "小窗尺寸",
            f"{small.get('w',200)} × {small.get('h',150)}", arrow=True, action="openSizesMenu:")
        # 4. 三个 toggle / 状态行
        proxy_label = self._proxy_label(proxy)
        proxy_row = self._build_proxy_row(proxy, proxy_label)
        pin_row = self._build_toggle_row("📌", C_ORANGE, "窗口置顶", "浮于其他 App 之上",
            pinned, "togglePin:")
        # incog_row = self._build_toggle_row("👁", C_PURPLE, "无痕模式", "关闭 App 即清 Cookie",
        #     False, "toggleIncognito:")
        # 5. 滑块
        gap_slider = self._build_slider("📏 窗口间距", f"{layout.get('gap',8)} px",
            int(layout.get('gap', 8)), 0, 30, "onGapChange:")
        op_slider = self._build_slider("💧 不透明度", f"{int(alpha*100)}%",
            int(alpha*100), 20, 100, "onOpacityChange:")
        # 6. 摆放控制
        layout_block = self._build_layout_block(layout)
        # 7. Quick actions
        quick = self._build_quick_actions()
        # 8. Header
        header = self._build_header(profile, wn)

        # 自顶向下叠子视图（每个组件都返回 NSView）
        components = [
            header,
            self._sep(),
            quick,
            self._sep_label("摆放"),
            layout_block,
            self._sep(),
            gap_slider,
            op_slider,
            self._sep(),
            proxy_row,
            pin_row,
            self._sep(),
            sub_size,
            sub_sites,
            sub_input,
            sub_chrome,
            sub_safari,
            sub_1pass,
            self._sep(),
            settings_row,
            footer,
        ]

        # 计算总高
        total_h = sum(c.frame().size.height for c in components)
        # 让 popover 内容控制高度
        self._root.setFrameSize_(NSMakeSize(self.W, total_h))

        # 自顶向下摆放
        y = total_h
        for c in components:
            h = c.frame().size.height
            y -= h
            c.setFrame_(NSMakeRect(0, y, self.W, h))
            self._root.addSubview_(c)

    # ── 组件构造 ─────────────────────────────
    def _sep(self):
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, 0.5))
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(C_HAIR.CGColor())
        return v

    def _sep_label(self, text):
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, 22))
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(16, 4, self.W - 32, 14))
        lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
        lbl.setEditable_(False); lbl.setSelectable_(False)
        lbl.setStringValue_(text)
        lbl.setFont_(NSFont.boldSystemFontOfSize_(10))
        lbl.setTextColor_(C_LABEL3)
        v.addSubview_(lbl)
        return v

    def _build_header(self, profile, win_count):
        h = 60
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        v.setWantsLayer_(True)
        # 渐变背景
        from AppKit import NSGradient
        v.layer().setBackgroundColor_(_color(255, 169, 77, 0.06).CGColor())

        avatar = IconChip.alloc().initWithSize_emoji_color_(
            40, "🐱", _color(255, 169, 77)
        )
        avatar.setFrame_(NSMakeRect(14, 10, 40, 40))
        v.addSubview_(avatar)

        name = NSTextField.alloc().initWithFrame_(NSMakeRect(64, 28, self.W - 80, 20))
        name.setBezeled_(False); name.setDrawsBackground_(False)
        name.setEditable_(False); name.setSelectable_(False)
        name_str = profile.get("name", "默认")
        name.setStringValue_(name_str)
        name.setFont_(NSFont.boldSystemFontOfSize_(14))
        name.setTextColor_(C_LABEL)
        v.addSubview_(name)

        meta = NSTextField.alloc().initWithFrame_(NSMakeRect(64, 10, self.W - 80, 16))
        meta.setBezeled_(False); meta.setDrawsBackground_(False)
        meta.setEditable_(False); meta.setSelectable_(False)
        mode_emoji = "⚒️" if profile.get("mode") == "work" else "🌈"
        mode_text = "工作模式" if profile.get("mode") == "work" else "摸鱼模式"
        meta.setStringValue_(f"{mode_emoji} {mode_text}  ·  {win_count} 个窗口")
        meta.setFont_(NSFont.systemFontOfSize_(11))
        meta.setTextColor_(C_LABEL3)
        v.addSubview_(meta)

        # 右上角：切换工作区按钮
        switch_btn = NSButton.alloc().initWithFrame_(NSMakeRect(self.W - 92, 16, 80, 28))
        switch_btn.setTitle_("切换工作区")
        switch_btn.setBezelStyle_(11)  # NSBezelStyleTexturedRounded
        switch_btn.setFont_(NSFont.systemFontOfSize_(11))
        switch_btn.setTarget_(self._sb)
        switch_btn.setAction_("openLauncher:")
        v.addSubview_(switch_btn)

        return v

    def _build_quick_actions(self):
        h = 64
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        items = [
            ("👁", C_BLUE,   "显示/隐藏", "qaToggleWindow:"),
            ("⊕", C_GREEN,  "新窗口",    "doNewWindow:"),
            ("⇄", C_ORANGE, "整理",      "doRearrange:"),
            ("🏠", C_PURPLE, "首页",      "qaHome:"),
        ]
        ICON_SZ = 26   # 图标缩小，跟 mockup 接近
        col_w = (self.W - 16) / len(items)
        for i, (emoji, color, label, action) in enumerate(items):
            x = 8 + i * col_w
            # 整列点击区
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, 2, col_w, h - 4))
            btn.setBordered_(False)
            btn.setTransparent_(True)
            btn.setTitle_("")
            btn.setTarget_(self._sb)
            btn.setAction_(action)
            v.addSubview_(btn)
            # 图标
            icon_x = x + (col_w - ICON_SZ) / 2
            icon_y = h - ICON_SZ - 18      # 顶部留 8 + 图标 26 + 间距 4 + 标签
            chip = IconChip.alloc().initWithSize_emoji_color_(ICON_SZ, emoji, color)
            chip.setFrame_(NSMakeRect(icon_x, icon_y, ICON_SZ, ICON_SZ))
            v.addSubview_(chip)
            # 标签
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(x, 4, col_w, 14))
            lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
            lbl.setEditable_(False); lbl.setSelectable_(False)
            lbl.setAlignment_(2)
            lbl.setStringValue_(label)
            lbl.setFont_(NSFont.systemFontOfSize_(10.5))
            lbl.setTextColor_(C_LABEL2)
            v.addSubview_(lbl)
        return v

    def _build_layout_block(self, layout):
        # ★ 重新计算高度严格匹配内容
        # arrow grid 3 行 + 间距 + segmented + padding
        cell = 28; gap = 3
        grid_h = cell * 3 + gap * 2          # 90
        seg_h  = 28
        v_pad_top = 10                        # 顶部留白
        v_pad_mid = 10                        # arrow grid 与 segmented 间
        v_pad_bot = 10                        # 底部留白
        h = v_pad_top + grid_h + v_pad_mid + seg_h + v_pad_bot   # 148

        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))

        # 3x3 方向键盘（macOS y 轴向上）
        cur_edge = layout.get("edge", "left")
        grid_w = cell * 3 + gap * 2
        grid_x = (self.W - grid_w) / 2
        # 底部行 y（↓所在的 y）
        bot_y = v_pad_bot + seg_h + v_pad_mid
        mid_y = bot_y + cell + gap
        top_y = bot_y + (cell + gap) * 2

        def make_dir_btn(emoji, edge, gx, gy):
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(gx, gy, cell, cell))
            btn.setTitle_(emoji)
            btn.setBordered_(False)
            btn.setWantsLayer_(True)
            btn.layer().setCornerRadius_(6)
            if edge == cur_edge:
                btn.layer().setBackgroundColor_(_color(0, 113, 227, 0.12).CGColor())
                btn.layer().setBorderWidth_(1.5)
                btn.layer().setBorderColor_(C_BLUE.CGColor())
            else:
                btn.layer().setBackgroundColor_(C_FILL1.CGColor())
            btn.setFont_(NSFont.systemFontOfSize_(13))
            btn.setTarget_(self._sb)
            btn.setAction_("setLayoutEdgeFromTag:")
            edge_to_tag = {"left": 1, "right": 2, "top": 3, "bottom": 4}
            btn.setTag_(edge_to_tag[edge])
            return btn

        # ↑（顶行中列）
        v.addSubview_(make_dir_btn("↑", "top",    grid_x + cell + gap, top_y))
        # ←（中行左列）
        v.addSubview_(make_dir_btn("←", "left",   grid_x,              mid_y))
        # 中心标签
        center_x = grid_x + cell + gap
        center_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(center_x, mid_y, cell, cell))
        center_lbl.setBezeled_(False); center_lbl.setDrawsBackground_(False)
        center_lbl.setEditable_(False); center_lbl.setSelectable_(False)
        center_lbl.setAlignment_(2)
        center_lbl.setStringValue_("竖列" if cur_edge in ("left", "right") else "横向")
        center_lbl.setFont_(NSFont.systemFontOfSize_(10))
        center_lbl.setTextColor_(C_LABEL3)
        v.addSubview_(center_lbl)
        # →（中行右列）
        v.addSubview_(make_dir_btn("→", "right",  grid_x + (cell + gap) * 2, mid_y))
        # ↓（底行中列）
        v.addSubview_(make_dir_btn("↓", "bottom", grid_x + cell + gap, bot_y))

        # 平铺/叠放 segmented control（在 v_pad_bot 上方）
        cur_style = layout.get("style", "tile")
        seg_y = v_pad_bot
        seg_h = 28
        seg_w = self.W - 32
        for i, (label, style) in enumerate([("▥ 平铺", "tile"), ("▤ 叠放", "cascade")]):
            bw = (seg_w - 4) / 2
            bx = 16 + i * (bw + 4)
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(bx, seg_y, bw, seg_h))
            btn.setTitle_(label)
            btn.setBordered_(False)
            btn.setWantsLayer_(True)
            btn.layer().setCornerRadius_(7)
            if style == cur_style:
                btn.layer().setBackgroundColor_(_color(0, 113, 227, 0.12).CGColor())
                btn.layer().setBorderWidth_(1.0)
                btn.layer().setBorderColor_(C_BLUE.CGColor())
            else:
                btn.layer().setBackgroundColor_(C_FILL1.CGColor())
            btn.setFont_(NSFont.systemFontOfSize_(12))
            btn.setTarget_(self._sb)
            btn.setAction_("setLayoutStyleFromTag:")
            btn.setTag_(1 if style == "tile" else 2)
            v.addSubview_(btn)

        return v

    def _build_slider(self, name, value_str, value, mn, mx, action):
        h = 44
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        # 名称
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(16, 22, self.W - 80, 16))
        lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
        lbl.setEditable_(False); lbl.setSelectable_(False)
        lbl.setStringValue_(name)
        lbl.setFont_(NSFont.systemFontOfSize_(12))
        lbl.setTextColor_(C_LABEL)
        v.addSubview_(lbl)
        # 值
        val = NSTextField.alloc().initWithFrame_(NSMakeRect(self.W - 70, 22, 54, 16))
        val.setBezeled_(False); val.setDrawsBackground_(False)
        val.setEditable_(False); val.setSelectable_(False)
        val.setStringValue_(value_str)
        val.setAlignment_(2)
        val.setFont_(NSFont.systemFontOfSize_(11))
        val.setTextColor_(C_LABEL3)
        v.addSubview_(val)
        # 滑块
        sl = NSSlider.alloc().initWithFrame_(NSMakeRect(16, 4, self.W - 32, 18))
        sl.setMinValue_(mn); sl.setMaxValue_(mx); sl.setDoubleValue_(value)
        sl.setContinuous_(True)
        sl.setTarget_(self._sb)
        sl.setAction_(action)
        v.addSubview_(sl)
        return v

    def _proxy_label(self, p):
        t = p.get("type", "direct")
        if t in ("socks5", "http"):
            return f"{t} {p.get('host', '127.0.0.1')}:{p.get('port', '')}"
        if t == "system":
            return "系统代理"
        return "直连（本地网络）"

    def _build_proxy_row(self, proxy, label_str):
        h = 50
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        # 整行点击
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        btn.setBordered_(False); btn.setTitle_("")
        btn.setTarget_(self._sb)
        btn.setAction_("editProxy:")
        v.addSubview_(btn)

        # 图标
        chip = IconChip.alloc().initWithSize_emoji_color_(22, "🌐", C_GREEN)
        chip.setFrame_(NSMakeRect(16, 14, 22, 22))
        v.addSubview_(chip)
        # 标题
        title = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 26, self.W - 130, 14))
        title.setBezeled_(False); title.setDrawsBackground_(False)
        title.setEditable_(False); title.setSelectable_(False)
        title.setStringValue_("代理")
        title.setFont_(NSFont.systemFontOfSize_(12)); title.setTextColor_(C_LABEL)
        v.addSubview_(title)
        # 副标题
        sub = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 8, self.W - 130, 16))
        sub.setBezeled_(False); sub.setDrawsBackground_(False)
        sub.setEditable_(False); sub.setSelectable_(False)
        sub.setStringValue_(label_str)
        sub.setFont_(NSFont.systemFontOfSize_(10.5)); sub.setTextColor_(C_LABEL3)
        v.addSubview_(sub)
        # 状态徽章
        ptype = proxy.get("type", "direct")
        badge_color = C_GREEN if ptype in ("socks5", "http") else C_GRAY
        badge_text = "已配置" if ptype in ("socks5", "http") else "直连"
        badge = NSView.alloc().initWithFrame_(NSMakeRect(self.W - 76, 16, 60, 18))
        badge.setWantsLayer_(True)
        badge.layer().setCornerRadius_(9)
        badge.layer().setBackgroundColor_(badge_color.CGColor())
        bl = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 1, 60, 14))
        bl.setBezeled_(False); bl.setDrawsBackground_(False)
        bl.setEditable_(False); bl.setSelectable_(False)
        bl.setAlignment_(2); bl.setStringValue_(badge_text)
        bl.setFont_(NSFont.boldSystemFontOfSize_(10)); bl.setTextColor_(NSColor.whiteColor())
        badge.addSubview_(bl)
        v.addSubview_(badge)
        return v

    def _build_toggle_row(self, emoji, color, title, sub_text, is_on, action):
        h = 50
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        # 整行可点（用按钮覆盖左侧文字区域，让 toggle 自身可独立点）
        chip = IconChip.alloc().initWithSize_emoji_color_(22, emoji, color)
        chip.setFrame_(NSMakeRect(16, 14, 22, 22))
        v.addSubview_(chip)
        title_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 26, self.W - 110, 14))
        title_lbl.setBezeled_(False); title_lbl.setDrawsBackground_(False)
        title_lbl.setEditable_(False); title_lbl.setSelectable_(False)
        title_lbl.setStringValue_(title)
        title_lbl.setFont_(NSFont.systemFontOfSize_(12)); title_lbl.setTextColor_(C_LABEL)
        v.addSubview_(title_lbl)
        sub_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 8, self.W - 110, 16))
        sub_lbl.setBezeled_(False); sub_lbl.setDrawsBackground_(False)
        sub_lbl.setEditable_(False); sub_lbl.setSelectable_(False)
        sub_lbl.setStringValue_(sub_text)
        sub_lbl.setFont_(NSFont.systemFontOfSize_(10.5)); sub_lbl.setTextColor_(C_LABEL3)
        v.addSubview_(sub_lbl)
        # 用 NSSwitch（macOS 10.15+）
        try:
            from AppKit import NSSwitch
            sw = NSSwitch.alloc().initWithFrame_(NSMakeRect(self.W - 56, 14, 40, 22))
            sw.setState_(1 if is_on else 0)
            sw.setTarget_(self._sb)
            sw.setAction_(action)
            v.addSubview_(sw)
        except Exception:
            # 老系统 fallback：复选框
            from AppKit import NSButton, NSSwitchButton
            sw = NSButton.alloc().initWithFrame_(NSMakeRect(self.W - 60, 18, 50, 20))
            sw.setButtonType_(NSSwitchButton)
            sw.setTitle_("")
            sw.setState_(1 if is_on else 0)
            sw.setTarget_(self._sb)
            sw.setAction_(action)
            v.addSubview_(sw)
        return v

    def _build_row(self, emoji, color, title, sub_text, arrow=False, kbd=False, action=None):
        h = 46
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        if action:
            btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
            btn.setBordered_(False); btn.setTitle_("")
            btn.setTarget_(self._sb)
            btn.setAction_(action)
            v.addSubview_(btn)
        chip = IconChip.alloc().initWithSize_emoji_color_(22, emoji, color)
        chip.setFrame_(NSMakeRect(16, 12, 22, 22))
        v.addSubview_(chip)
        if sub_text:
            title_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 24, self.W - 110, 14))
            title_lbl.setBezeled_(False); title_lbl.setDrawsBackground_(False)
            title_lbl.setEditable_(False); title_lbl.setSelectable_(False)
            title_lbl.setStringValue_(title)
            title_lbl.setFont_(NSFont.systemFontOfSize_(12)); title_lbl.setTextColor_(C_LABEL)
            v.addSubview_(title_lbl)
            sub_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 6, self.W - 110, 16))
            sub_lbl.setBezeled_(False); sub_lbl.setDrawsBackground_(False)
            sub_lbl.setEditable_(False); sub_lbl.setSelectable_(False)
            sub_lbl.setStringValue_(sub_text)
            sub_lbl.setFont_(NSFont.systemFontOfSize_(10.5)); sub_lbl.setTextColor_(C_LABEL3)
            v.addSubview_(sub_lbl)
        else:
            title_lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(46, 14, self.W - 110, 18))
            title_lbl.setBezeled_(False); title_lbl.setDrawsBackground_(False)
            title_lbl.setEditable_(False); title_lbl.setSelectable_(False)
            title_lbl.setStringValue_(title)
            title_lbl.setFont_(NSFont.systemFontOfSize_(13)); title_lbl.setTextColor_(C_LABEL)
            v.addSubview_(title_lbl)
        # 右侧
        if arrow:
            ar = NSTextField.alloc().initWithFrame_(NSMakeRect(self.W - 28, 14, 16, 18))
            ar.setBezeled_(False); ar.setDrawsBackground_(False)
            ar.setEditable_(False); ar.setSelectable_(False)
            ar.setStringValue_("›"); ar.setFont_(NSFont.systemFontOfSize_(16))
            ar.setTextColor_(C_LABEL3); ar.setAlignment_(2)
            v.addSubview_(ar)
        elif kbd:
            kb = NSTextField.alloc().initWithFrame_(NSMakeRect(self.W - 50, 16, 36, 16))
            kb.setBezeled_(False); kb.setEditable_(False); kb.setSelectable_(False)
            kb.setDrawsBackground_(True)
            kb.setBackgroundColor_(C_FILL1)
            kb.setStringValue_(sub_text or "")
            kb.setFont_(NSFont.systemFontOfSize_(10))
            kb.setTextColor_(C_LABEL2); kb.setAlignment_(2)
            kb.setWantsLayer_(True)
            kb.layer().setCornerRadius_(4)
            v.addSubview_(kb)
        return v

    def _build_footer(self, cfg):
        h = 36
        v = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self.W, h))
        v.setWantsLayer_(True)
        v.layer().setBackgroundColor_(C_BG_SEC.CGColor())

        # 左侧：快捷键提示
        from config import hotkey_display
        try:
            tk = hotkey_display(cfg.get("toggle_hotkey", {}))
            rk = hotkey_display(cfg.get("rearrange_hotkey", {}))
            tip = f"{tk} 唤起 · {rk} 整理"
        except Exception:
            tip = "⌥~ 唤起 · ⌘⌥R 整理"
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(16, 10, self.W - 80, 16))
        lbl.setBezeled_(False); lbl.setDrawsBackground_(False)
        lbl.setEditable_(False); lbl.setSelectable_(False)
        lbl.setStringValue_(tip)
        lbl.setFont_(NSFont.systemFontOfSize_(10))
        lbl.setTextColor_(C_LABEL3)
        v.addSubview_(lbl)

        # 右侧：退出按钮
        quit_btn = NSButton.alloc().initWithFrame_(NSMakeRect(self.W - 56, 6, 44, 24))
        quit_btn.setBordered_(False)
        quit_btn.setTitle_("退出")
        quit_btn.setFont_(NSFont.systemFontOfSize_(12))
        from AppKit import NSAttributedString
        from Foundation import NSDictionary
        try:
            attrs = {
                "NSColor": C_RED,
                "NSFont": NSFont.systemFontOfSize_(12),
            }
            ats = NSAttributedString.alloc().initWithString_attributes_("退出", attrs)
            quit_btn.setAttributedTitle_(ats)
        except Exception:
            pass
        quit_btn.setTarget_(self._sb)
        quit_btn.setAction_("doQuit:")
        v.addSubview_(quit_btn)

        return v


# ─── StatusBarController（菜单栏控制器）───────
class StatusBarController(NSObject):

    def initWithWindow_appDelegate_(self, window, app_delegate):
        self = objc.super(StatusBarController, self).init()
        if self is None:
            return None
        self._window = window
        self._app_delegate = app_delegate
        self._status_item = None
        self._popover = None
        self._popover_vc = None
        self._setup_status_bar()
        return self

    def initWithWindow_(self, window):
        return self.initWithWindow_appDelegate_(window, None)

    def _setup_status_bar(self):
        status_bar = NSStatusBar.systemStatusBar()
        self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
        button = self._status_item.button()
        # 小猫 PNG 图标
        try:
            png_path = NSBundle.mainBundle().pathForResource_ofType_("menubar_kitten@2x", "png")
            if not png_path:
                import os
                here = os.path.dirname(os.path.abspath(__file__))
                png_path = os.path.join(here, "resources", "menubar_kitten@2x.png")
            img = NSImage.alloc().initWithContentsOfFile_(png_path)
            if img is not None:
                img.setSize_(NSMakeSize(18, 18))
                button.setImage_(img)
                button.setImagePosition_(2)
            else:
                raise RuntimeError("img None")
        except Exception:
            button.setTitle_("🐱")
            button.setFont_(NSFont.systemFontOfSize_(14))

        # 按钮点击触发 popover
        button.setTarget_(self)
        button.setAction_("togglePopover:")

    def rebuild_menu(self):
        """popover 模式下，仅触发 vc 重建"""
        if self._popover_vc is not None:
            self._popover_vc._refresh()

    # ── popover 显示/隐藏 ──────────────────
    @objc.IBAction
    def togglePopover_(self, sender):
        if self._popover is None:
            self._popover_vc = PopoverVC.alloc().initWithStatusBar_(self)
            self._popover = NSPopover.alloc().init()
            self._popover.setContentViewController_(self._popover_vc)
            self._popover.setBehavior_(NSPopoverBehaviorTransient)
        else:
            # 每次重新打开都刷一次内容
            self._popover_vc._refresh()
            # 同步 popover 内容尺寸
            self._popover.setContentSize_(self._popover_vc.view().frame().size)
        if self._popover.isShown():
            self._popover.performClose_(sender)
        else:
            btn = self._status_item.button()
            self._popover.setContentSize_(self._popover_vc.view().frame().size)
            self._popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, NSRectEdgeMinY
            )

    # ── 旧菜单 actions（popover 调用同样接口）────
    @objc.IBAction
    def toggleWindow_(self, sender):
        if self._window.isVisible():
            self._window.orderOut_(None)
        else:
            if hasattr(self._window, "relocateToCursorScreen"):
                self._window.relocateToCursorScreen()
            self._window.makeKeyAndOrderFront_(None)
        self._close_popover()

    @objc.IBAction
    def qaToggleWindow_(self, sender):
        self.toggleWindow_(sender)

    @objc.IBAction
    def qaHome_(self, sender):
        try:
            if hasattr(self._window, "goHome"):
                self._window.goHome()
        except Exception as e:
            NSLog(f"qaHome_ err: {e}")
        self._close_popover()

    @objc.IBAction
    def doNewWindow_(self, sender):
        try:
            from boss_manager import get_active_boss
            boss = get_active_boss()
            if boss is None or self._app_delegate is None:
                return
            from browser import StealthWindow
            child = StealthWindow.alloc().initWithApp_(self._app_delegate)
            boss.add_child(child)
            child.makeKeyAndOrderFront_(None)
        except Exception as e:
            NSLog(f"doNewWindow_ err: {e}")
        self._close_popover()

    @objc.IBAction
    def doRearrange_(self, sender):
        try:
            from boss_manager import get_active_boss
            boss = get_active_boss()
            if boss is not None:
                boss.layout.reflow()
        except Exception as e:
            NSLog(f"doRearrange_ err: {e}")

    # ── 摆放 ───────────────────────────────
    @objc.IBAction
    def setLayoutEdgeFromTag_(self, sender):
        tag_to_edge = {1: "left", 2: "right", 3: "top", 4: "bottom"}
        edge = tag_to_edge.get(int(sender.tag()), "left")
        try:
            from boss_manager import get_active_boss
            boss = get_active_boss()
            if boss is not None:
                boss.layout.set_edge(edge)
                if self._app_delegate is not None:
                    cfg = self._app_delegate.config()
                    cfg.setdefault("layout", {})["edge"] = edge
                    self._app_delegate.applyConfig_(cfg)
                self.rebuild_menu()
        except Exception as e:
            NSLog(f"setLayoutEdge err: {e}")

    @objc.IBAction
    def setLayoutStyleFromTag_(self, sender):
        style = "tile" if int(sender.tag()) == 1 else "cascade"
        try:
            from boss_manager import get_active_boss
            boss = get_active_boss()
            if boss is not None:
                boss.layout.set_style(style)
                if self._app_delegate is not None:
                    cfg = self._app_delegate.config()
                    cfg.setdefault("layout", {})["style"] = style
                    self._app_delegate.applyConfig_(cfg)
                self.rebuild_menu()
        except Exception as e:
            NSLog(f"setLayoutStyle err: {e}")

    # ── 滑块 ───────────────────────────────
    @objc.IBAction
    def onGapChange_(self, sender):
        try:
            v = int(sender.doubleValue())
            from boss_manager import get_active_boss
            boss = get_active_boss()
            if boss is not None:
                boss.layout.set_gap(v)
            if self._app_delegate is not None:
                cfg = self._app_delegate.config()
                cfg.setdefault("layout", {})["gap"] = v
                self._app_delegate.applyConfig_(cfg)
        except Exception as e:
            NSLog(f"onGapChange_ err: {e}")

    @objc.IBAction
    def onOpacityChange_(self, sender):
        try:
            v = sender.doubleValue() / 100.0
            if hasattr(self._window, "setOpacityLevel_"):
                self._window.setOpacityLevel_(v)
        except Exception as e:
            NSLog(f"onOpacityChange_ err: {e}")

    # ── 置顶 toggle ───────────────────────
    @objc.IBAction
    def togglePin_(self, sender):
        try:
            if hasattr(self._window, "doTogglePin_"):
                self._window.doTogglePin_(sender)
        except Exception as e:
            NSLog(f"togglePin_ err: {e}")

    # ── 二级菜单 ───────────────────────────
    @objc.IBAction
    def openSitesMenu_(self, sender):
        """弹常用网站子菜单"""
        m = NSMenu.alloc().initWithTitle_("常用网站")
        for name, url in [
            ("百度", "https://www.baidu.com"),
            ("微博", "https://m.weibo.cn"),
            ("知乎", "https://www.zhihu.com"),
            ("B站", "https://m.bilibili.com"),
            ("YouTube", "https://www.youtube.com"),
            ("GitHub", "https://github.com"),
            ("ChatGPT", "https://chat.openai.com"),
        ]:
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(name, "openSite:", "")
            it.setTarget_(self); it.setRepresentedObject_(url)
            m.addItem_(it)
        # 在按钮位置弹出
        try:
            from AppKit import NSEvent
            event = NSApplication.sharedApplication().currentEvent()
            if event:
                NSMenu.popUpContextMenu_withEvent_forView_(m, event, sender)
        except Exception as e:
            NSLog(f"openSitesMenu_ err: {e}")

    @objc.IBAction
    def openSizesMenu_(self, sender):
        m = NSMenu.alloc().initWithTitle_("小窗尺寸")
        try:
            from config import SMALL_SIZE_PRESETS
            cur_w = getattr(self._window, "_small_w", 200)
            cur_h = getattr(self._window, "_small_h", 150)
            for label, w, h in SMALL_SIZE_PRESETS:
                sub = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, "setSmallSize:", "")
                sub.setTarget_(self)
                sub.setRepresentedObject_(NSNumber.numberWithUnsignedLongLong_(w * 100000 + h))
                if w == cur_w and h == cur_h:
                    sub.setState_(1)
                m.addItem_(sub)
            m.addItem_(NSMenuItem.separatorItem())
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("📐 自定义...", "editCustomSize:", "")
            it.setTarget_(self)
            m.addItem_(it)
        except Exception as e:
            NSLog(f"openSizesMenu_ build err: {e}")
        try:
            event = NSApplication.sharedApplication().currentEvent()
            if event:
                NSMenu.popUpContextMenu_withEvent_forView_(m, event, sender)
        except Exception as e:
            NSLog(f"openSizesMenu_ pop err: {e}")

    # ── 高级设置（弹老菜单/对话框）──────────
    @objc.IBAction
    def openAdvanced_(self, sender):
        m = NSMenu.alloc().initWithTitle_("高级设置")
        for label, action in [
            ("📥  导入浏览器书签", "importBookmarks:"),
            ("⌨️  快捷键设置...", "editHotkeys:"),
            ("📐  自定义小窗尺寸...", "editCustomSize:"),
            ("🌐  代理设置...", "editProxy:"),
        ]:
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, action, "")
            it.setTarget_(self)
            m.addItem_(it)
        try:
            event = NSApplication.sharedApplication().currentEvent()
            if event:
                NSMenu.popUpContextMenu_withEvent_forView_(m, event, sender)
        except Exception as e:
            NSLog(f"openAdvanced_ err: {e}")

    # ── 老 actions（弹对话框）─────────────
    @objc.IBAction
    def openURL_(self, sender):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("输入网址")
        alert.setInformativeText_("URL 或关键词，回车直达")
        alert.addButtonWithTitle_("前往"); alert.addButtonWithTitle_("取消")
        f = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 320, 24))
        f.setStringValue_("https://")
        alert.setAccessoryView_(f)
        if not self._window.isVisible():
            self._window.makeKeyAndOrderFront_(None)
        if alert.runModal() == NSAlertFirstButtonReturn:
            if f.stringValue():
                self._window.navigateTo_(f.stringValue())

    @objc.IBAction
    def setOpacity_(self, sender):
        try:
            tag = int(sender.tag())
        except Exception:
            tag = 0
        if 0 < tag <= 100:
            self._window.setOpacityLevel_(tag / 100.0)
            self.rebuild_menu()

    @objc.IBAction
    def setSmallSize_(self, sender):
        encoded = sender.representedObject()
        if encoded is None:
            return
        v = int(encoded)
        w = v // 100000; h = v % 100000
        if hasattr(self._window, "setSmallSizeW_h_"):
            self._window.setSmallSizeW_h_(w, h)
        if self._app_delegate is not None:
            cfg = self._app_delegate.config()
            cfg["small_window_size"] = {"w": w, "h": h}
            self._app_delegate.applyConfig_(cfg)
        self.rebuild_menu()

    @objc.IBAction
    def openSite_(self, sender):
        url = sender.representedObject()
        if url:
            if not self._window.isVisible():
                self._window.makeKeyAndOrderFront_(None)
            self._window.navigateTo_(url)

    @objc.IBAction
    def editHotkeys_(self, sender):
        if self._app_delegate is None:
            return
        cfg = self._app_delegate.config()
        alert = NSAlert.alloc().init()
        alert.setMessageText_("⌨️ 快捷键设置")
        alert.setInformativeText_("格式: cmd+alt+B  或  alt+~  或  cmd+shift+R")
        alert.addButtonWithTitle_("保存"); alert.addButtonWithTitle_("取消")
        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 340, 110))
        # toggle
        l1 = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 84, 110, 22))
        l1.setBezeled_(False); l1.setDrawsBackground_(False)
        l1.setEditable_(False); l1.setSelectable_(False)
        l1.setStringValue_("显示/隐藏:")
        container.addSubview_(l1)
        toggle_field = NSTextField.alloc().initWithFrame_(NSMakeRect(115, 82, 220, 24))
        toggle_field.setStringValue_(_hotkey_to_str(cfg["toggle_hotkey"]))
        container.addSubview_(toggle_field)
        # rearrange
        l2 = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 50, 110, 22))
        l2.setBezeled_(False); l2.setDrawsBackground_(False)
        l2.setEditable_(False); l2.setSelectable_(False)
        l2.setStringValue_("一键整理:")
        container.addSubview_(l2)
        rearr_field = NSTextField.alloc().initWithFrame_(NSMakeRect(115, 48, 220, 24))
        rearr_field.setStringValue_(_hotkey_to_str(cfg.get("rearrange_hotkey", {"modifiers": ["cmd","alt"], "key":"R"})))
        container.addSubview_(rearr_field)
        # quit
        l3 = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 16, 110, 22))
        l3.setBezeled_(False); l3.setDrawsBackground_(False)
        l3.setEditable_(False); l3.setSelectable_(False)
        l3.setStringValue_("退出 App:")
        container.addSubview_(l3)
        quit_field = NSTextField.alloc().initWithFrame_(NSMakeRect(115, 14, 220, 24))
        quit_field.setStringValue_(_hotkey_to_str(cfg["quit_hotkey"]))
        container.addSubview_(quit_field)

        alert.setAccessoryView_(container)
        if alert.runModal() != NSAlertFirstButtonReturn:
            return
        new_t = _str_to_hotkey(toggle_field.stringValue())
        new_r = _str_to_hotkey(rearr_field.stringValue())
        new_q = _str_to_hotkey(quit_field.stringValue())
        if not (new_t and new_r and new_q):
            err = NSAlert.alloc().init()
            err.setMessageText_("格式错误"); err.runModal()
            return
        cfg["toggle_hotkey"] = new_t
        cfg["rearrange_hotkey"] = new_r
        cfg["quit_hotkey"] = new_q
        self._app_delegate.applyConfig_(cfg)
        self.rebuild_menu()

    @objc.IBAction
    def editProxy_(self, sender):
        if self._app_delegate is None:
            return
        cfg = self._app_delegate.config()
        cur = (cfg.get("profile", {}) or {}).get("proxy", {}) or {"type": "direct"}
        alert = NSAlert.alloc().init()
        alert.setMessageText_("🌐 代理设置")
        alert.setInformativeText_(
            "格式：\n"
            "  direct                                  # 直连\n"
            "  socks5 127.0.0.1 1087\n"
            "  http   127.0.0.1 7890\n"
        )
        alert.addButtonWithTitle_("保存"); alert.addButtonWithTitle_("取消")
        if cur.get("type") in ("socks5", "http"):
            cur_str = f"{cur['type']} {cur.get('host', '127.0.0.1')} {cur.get('port', '')}"
        else:
            cur_str = "direct"
        f = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 24))
        f.setStringValue_(cur_str)
        alert.setAccessoryView_(f)
        if alert.runModal() != NSAlertFirstButtonReturn:
            return
        text = f.stringValue().strip()
        new_proxy = self._parse_proxy_str(text)
        if new_proxy is None:
            err = NSAlert.alloc().init()
            err.setMessageText_("格式错误"); err.runModal()
            return
        cfg.setdefault("profile", {})["proxy"] = new_proxy
        self._app_delegate.applyConfig_(cfg)
        self._reapply_proxy_to_active(new_proxy)
        self.rebuild_menu()

    def _parse_proxy_str(self, s):
        if not s:
            return None
        parts = s.split()
        head = parts[0].lower()
        if head == "direct":
            return {"type": "direct"}
        if head in ("socks5", "http") and len(parts) >= 3:
            try:
                return {"type": head, "host": parts[1], "port": int(parts[2])}
            except ValueError:
                return None
        return None

    def _reapply_proxy_to_active(self, proxy_dict):
        try:
            from boss_manager import all_bosses
            from proxy import apply_to_data_store
            from WebKit import WKWebsiteDataStore
            ds = WKWebsiteDataStore.defaultDataStore()
            apply_to_data_store(ds, proxy_dict)
            for boss in all_bosses():
                for w in boss.all_windows():
                    try:
                        w.reload()
                    except Exception:
                        pass
        except Exception as e:
            NSLog(f"_reapply_proxy_to_active err: {e}")

    @objc.IBAction
    def editCustomSize_(self, sender):
        cfg = self._app_delegate.config() if self._app_delegate else {}
        cur = cfg.get("small_window_size", {"w": 200, "h": 150})
        alert = NSAlert.alloc().init()
        alert.setMessageText_("📐 自定义小窗尺寸")
        alert.setInformativeText_("范围 60-800 px")
        alert.addButtonWithTitle_("应用"); alert.addButtonWithTitle_("取消")
        c = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 280, 60))
        l1 = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 36, 60, 22))
        l1.setBezeled_(False); l1.setDrawsBackground_(False)
        l1.setEditable_(False); l1.setSelectable_(False); l1.setStringValue_("宽:")
        c.addSubview_(l1)
        wf = NSTextField.alloc().initWithFrame_(NSMakeRect(60, 34, 80, 24))
        wf.setStringValue_(str(cur.get("w", 200)))
        c.addSubview_(wf)
        l2 = NSTextField.alloc().initWithFrame_(NSMakeRect(150, 36, 30, 22))
        l2.setBezeled_(False); l2.setDrawsBackground_(False)
        l2.setEditable_(False); l2.setSelectable_(False); l2.setStringValue_("高:")
        c.addSubview_(l2)
        hf = NSTextField.alloc().initWithFrame_(NSMakeRect(180, 34, 80, 24))
        hf.setStringValue_(str(cur.get("h", 150)))
        c.addSubview_(hf)
        alert.setAccessoryView_(c)
        if alert.runModal() != NSAlertFirstButtonReturn:
            return
        try:
            w = int(wf.stringValue()); h = int(hf.stringValue())
        except ValueError:
            return
        if not (60 <= w <= 800 and 60 <= h <= 800):
            return
        cfg["small_window_size"] = {"w": w, "h": h}
        self._app_delegate.applyConfig_(cfg)
        if hasattr(self._window, "setSmallSizeW_h_"):
            self._window.setSmallSizeW_h_(w, h)
        self.rebuild_menu()

    @objc.IBAction
    def openInSafari_(self, sender):
        """把当前 webview 的页面交给 Safari 打开"""
        try:
            wv = getattr(self._window, "_webview", None)
            if wv is None:
                return
            url = wv.URL()
            if url is None:
                return
            url_str = str(url.absoluteString())
            from AppKit import NSWorkspace
            from Foundation import NSURL
            target = NSURL.URLWithString_(url_str)
            if target:
                NSWorkspace.sharedWorkspace().openURL_(target)
                NSLog(f"✓ Safari 打开: {url_str}")
            self._close_popover()
        except Exception as e:
            NSLog(f"openInSafari_ err: {e}")

    @objc.IBAction
    def openInChrome_(self, sender):
        """把当前页扔给系统 Chrome（带所有扩展 + 登录态）"""
        try:
            wv = getattr(self._window, "_webview", None)
            if wv is None or wv.URL() is None:
                return
            url_str = str(wv.URL().absoluteString())
            from AppKit import NSWorkspace
            from Foundation import NSURL
            ws = NSWorkspace.sharedWorkspace()
            target_url = NSURL.URLWithString_(url_str)
            # 找 Chrome 应用
            chrome_paths = [
                "/Applications/Google Chrome.app",
                "/Applications/Google Chrome Beta.app",
                "/Applications/Google Chrome Canary.app",
                "/Applications/Brave Browser.app",
                "/Applications/Microsoft Edge.app",
                "/Applications/Arc.app",
            ]
            import os
            chrome_app = None
            chrome_name = ""
            for p in chrome_paths:
                if os.path.isdir(p):
                    chrome_app = NSURL.fileURLWithPath_(p)
                    chrome_name = os.path.basename(p).replace(".app", "")
                    break
            if chrome_app is None:
                a = NSAlert.alloc().init()
                a.setMessageText_("未找到 Chrome / Brave / Edge / Arc")
                a.setInformativeText_("请安装 Chromium 系列浏览器后重试")
                a.runModal()
                return
            try:
                # macOS 11+: openURLs:withApplicationAtURL:configuration:completionHandler:
                from AppKit import NSWorkspaceOpenConfiguration
                ws.openURLs_withApplicationAtURL_configuration_completionHandler_(
                    [target_url], chrome_app,
                    NSWorkspaceOpenConfiguration.configuration(), None,
                )
            except Exception:
                # fallback：用 open -a 命令
                import subprocess
                subprocess.Popen(["open", "-a", chrome_name, url_str])
            NSLog(f"✓ {chrome_name} 打开: {url_str}")
            self._close_popover()
        except Exception as e:
            NSLog(f"openInChrome_ err: {e}")

    @objc.IBAction
    def importBookmarks_(self, sender):
        """手动触发书签导入 + 报告结果"""
        try:
            from bookmarks import import_first_available, find_sources
            sources = find_sources()
            if not sources:
                a = NSAlert.alloc().init()
                a.setMessageText_("未找到浏览器书签")
                a.setInformativeText_(
                    "已查找 Chrome / Edge / Brave / Arc，都没找到 Bookmarks 文件。\n"
                    "请打开浏览器至少添加一个书签。"
                )
                a.runModal()
                return
            data = import_first_available()
            n = data.get("total", 0)
            g = len(data.get("groups", []))
            br = data.get("browser", "?")
            a = NSAlert.alloc().init()
            a.setMessageText_(f"✓ 已导入 {n} 个书签")
            a.setInformativeText_(f"来源: {br}\n分组: {g} 个\n\n点首页按钮即可看到（仅工作模式生效）")
            a.runModal()
            # 触发当前窗口刷新首页
            try:
                if hasattr(self._window, "goHome"):
                    self._window.goHome()
            except Exception:
                pass
        except Exception as e:
            NSLog(f"importBookmarks_ err: {e}")
            a = NSAlert.alloc().init()
            a.setMessageText_("导入失败")
            a.setInformativeText_(str(e))
            a.runModal()

    @objc.IBAction
    def fill1Password_(self, sender):
        """从 1Password CLI 选 item，自动填充当前页面输入框"""
        try:
            import onepass
            if not onepass.is_available():
                a = NSAlert.alloc().init()
                a.setMessageText_("未安装 1Password CLI")
                a.setInformativeText_(
                    "Meowser 用 op 命令行集成 1Password（macOS WebKit 不支持 Safari 扩展）。\n\n"
                    "安装：brew install --cask 1password-cli\n"
                    "然后在 1Password app 设置里勾选「集成 → 命令行连接」"
                )
                a.runModal()
                return
            if not onepass.is_signed_in():
                a = NSAlert.alloc().init()
                a.setMessageText_("1Password 未登录")
                a.setInformativeText_("请先在 1Password app 解锁，并打开「集成 → 与命令行集成」")
                a.runModal()
                return

            items = onepass.list_logins()
            if not items:
                a = NSAlert.alloc().init()
                a.setMessageText_("没有 Login 类型的 item")
                a.runModal()
                return

            # 让用户选 item — 用 NSAlert + accessory popup
            from AppKit import NSPopUpButton
            alert = NSAlert.alloc().init()
            alert.setMessageText_("🔐 选择要填充的账号")
            cur_url = ""
            try:
                wv = getattr(self._window, "_webview", None)
                if wv and wv.URL():
                    cur_url = str(wv.URL().absoluteString())
            except Exception:
                pass
            alert.setInformativeText_(f"当前页面: {cur_url[:80]}")
            alert.addButtonWithTitle_("填充")
            alert.addButtonWithTitle_("取消")

            popup = NSPopUpButton.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 26))
            for name, iid, url in items[:200]:
                short_url = url.split("/")[2] if "://" in url else url
                popup.addItemWithTitle_(f"{name} · {short_url}")
            alert.setAccessoryView_(popup)

            if alert.runModal() != NSAlertFirstButtonReturn:
                return
            idx = popup.indexOfSelectedItem()
            if idx < 0 or idx >= len(items):
                return
            _, item_id, _ = items[idx]

            cred = onepass.get_credentials(item_id)
            if not cred:
                a = NSAlert.alloc().init()
                a.setMessageText_("无法读取该 item 的账号密码")
                a.runModal()
                return
            user, pwd = cred

            # inject JS
            wv = getattr(self._window, "_webview", None)
            if wv is None:
                return
            wv.evaluateJavaScript_completionHandler_(onepass.fill_js(user, pwd), None)
            self._close_popover()
        except Exception as e:
            NSLog(f"fill1Password_ err: {e}")

    @objc.IBAction
    def openLauncher_(self, sender):
        try:
            if self._app_delegate is not None and hasattr(self._app_delegate, "showLauncher"):
                self._app_delegate.showLauncher()
            self._close_popover()
        except Exception as e:
            NSLog(f"openLauncher_ err: {e}")

    @objc.IBAction
    def doQuit_(self, sender):
        NSApplication.sharedApplication().terminate_(None)

    def _close_popover(self):
        if self._popover and self._popover.isShown():
            self._popover.performClose_(None)
