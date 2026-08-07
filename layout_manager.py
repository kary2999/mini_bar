"""
Meowser — 摆放管理器
管理一组小窗（一个 Boss 下属的所有 Children）的自动排列
支持：方向 left/right/top/bottom × 样式 tile/cascade
"""

from AppKit import NSScreen
from Foundation import NSMakeRect


class LayoutManager:
    """
    管理一组 NSWindow 的自动布局
    所有窗口按"槽位顺序"排列
    """

    MARGIN = 16  # 距屏幕边缘的最小留白

    def __init__(self):
        self._windows = []        # 按顺序的窗口列表（小窗模式下被排列的）
        self._edge = "left"
        self._style = "tile"
        self._gap = 8
        self._auto_reflow = True

    # ── 配置 ─────────────────────────────────────
    def set_edge(self, edge):
        if edge in ("left", "right", "top", "bottom"):
            self._edge = edge
            self.reflow()

    def set_style(self, style):
        if style in ("tile", "cascade"):
            self._style = style
            self.reflow()

    def set_gap(self, gap):
        self._gap = max(0, int(gap))
        self.reflow()

    def set_auto_reflow(self, enabled):
        self._auto_reflow = bool(enabled)

    def get_state(self):
        return {
            "edge": self._edge,
            "style": self._style,
            "gap": self._gap,
            "auto_reflow": self._auto_reflow,
            "count": len(self._windows),
        }

    # ── 窗口管理 ────────────────────────────────
    def register(self, window):
        if window not in self._windows:
            self._windows.append(window)
            self.reflow()

    def unregister(self, window):
        if window in self._windows:
            self._windows.remove(window)
            if self._auto_reflow:
                self.reflow()

    def windows(self):
        return list(self._windows)

    # ── 核心：重新排列 ──────────────────────────
    def reflow(self):
        """根据当前 edge / style 重新摆放所有窗口"""
        if not self._windows:
            return
        # 只对当前是"小窗模式"的窗口排列；大窗（_is_big=True）不参与
        active = [w for w in self._windows if not getattr(w, "_is_big", False)]
        if not active:
            return

        screen = NSScreen.mainScreen().visibleFrame()
        m = self.MARGIN
        gap = self._gap
        sx, sy = screen.origin.x, screen.origin.y
        sw, sh = screen.size.width, screen.size.height

        if self._style == "tile":
            self._tile(active, sx, sy, sw, sh, m, gap)
        else:
            self._cascade(active, sx, sy, sw, sh, m)

    def _tile(self, wins, sx, sy, sw, sh, m, gap):
        """平铺：每个窗口完整可见"""
        edge = self._edge
        if edge in ("left", "right"):
            # 竖列：从上往下排
            x = sx + m if edge == "left" else None  # right 计算时再算
            cur_y_top = sy + sh - m  # 屏幕顶部 y 坐标（macOS y 向上为正）
            for w in wins:
                f = w.frame()
                ww, wh = f.size.width, f.size.height
                if edge == "right":
                    x = sx + sw - ww - m
                y = cur_y_top - wh
                w.setFrameOrigin_((x, y))
                cur_y_top = y - gap
        else:
            # 横向：从左往右排
            y = sy + m if edge == "bottom" else None
            cur_x = sx + m
            for w in wins:
                f = w.frame()
                ww, wh = f.size.width, f.size.height
                if edge == "top":
                    y = sy + sh - wh - m
                w.setFrameOrigin_((cur_x, y))
                cur_x += ww + gap

    def _cascade(self, wins, sx, sy, sw, sh, m):
        """叠放：每个窗口错位一个标题栏的位置"""
        offset_step = 24  # 每张牌错位 24px
        edge = self._edge

        # 取首张窗口尺寸作基准（叠放时通常它们尺寸接近）
        first = wins[0].frame()
        ww, wh = first.size.width, first.size.height

        if edge == "left":
            base_x = sx + m
            base_y = sy + sh - m - wh
            dx, dy = offset_step, -offset_step
        elif edge == "right":
            base_x = sx + sw - m - ww
            base_y = sy + sh - m - wh
            dx, dy = -offset_step, -offset_step
        elif edge == "top":
            base_x = sx + m
            base_y = sy + sh - m - wh
            dx, dy = offset_step, -offset_step
        else:  # bottom
            base_x = sx + m
            base_y = sy + m
            dx, dy = offset_step, offset_step

        for i, w in enumerate(wins):
            x = base_x + dx * i
            y = base_y + dy * i
            w.setFrameOrigin_((x, y))
            w.orderFront_(None)
