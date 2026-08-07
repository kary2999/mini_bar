"""
Meowser — Boss / Child 窗口层级管理
- 启动 App 后第一个窗口 = Boss（用户当前选定的 Profile）
- Boss 创建的所有窗口 = Children
- Children 共享 Boss 的 webdata 目录、代理、模式
- Children 由 Boss 的 LayoutManager 排队
- Boss 关闭 → 所有 Children 一起关闭
"""

from layout_manager import LayoutManager


class Boss:
    """一个 Boss 实例 = 一个用户启动的 Profile"""

    def __init__(self, profile_name="默认", profile_cfg=None):
        self.profile_name = profile_name
        self.profile_cfg = profile_cfg or {}
        self.layout = LayoutManager()
        self._main_window = None       # Boss 自己的主窗口
        self._child_windows = []       # 此 Boss 的所有子窗

    def set_main_window(self, win):
        self._main_window = win
        self.layout.register(win)

    def main_window(self):
        return self._main_window

    def add_child(self, win):
        if win is self._main_window:
            return
        if win not in self._child_windows:
            self._child_windows.append(win)
        self.layout.register(win)

    def remove_child(self, win):
        if win in self._child_windows:
            self._child_windows.remove(win)
        self.layout.unregister(win)

    def all_windows(self):
        out = []
        if self._main_window is not None:
            out.append(self._main_window)
        out.extend(self._child_windows)
        return out

    def close_all(self):
        for w in list(self._child_windows):
            try:
                w.close()
            except Exception:
                pass
        self._child_windows.clear()
        if self._main_window is not None:
            try:
                self._main_window.close()
            except Exception:
                pass
        self._main_window = None


# ─────── 全局 Boss 注册表 ───────
_bosses = []
_active_boss = None


def get_active_boss():
    return _active_boss


def set_active_boss(boss):
    global _active_boss
    _active_boss = boss


def create_boss(profile_name="默认", profile_cfg=None):
    boss = Boss(profile_name, profile_cfg)
    _bosses.append(boss)
    set_active_boss(boss)
    return boss


def all_bosses():
    return list(_bosses)


def find_boss_for_window(win):
    """根据 NSWindow 反查它属于哪个 Boss"""
    for b in _bosses:
        if win is b.main_window() or win in b._child_windows:
            return b
    return None
