#!/usr/bin/env python3
"""
Meowser — 浮动浏览器（Boss/Child + 启动器）
启动流程：
  1. App 启动 → 弹启动器（独立窗口）
  2. 用户选 profile → 创建 Boss → 打开主窗口
  3. 菜单栏 popover 提供日常控制 + "切换工作区" 入口
"""

import objc
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from Foundation import NSObject, NSLog, NSAutoreleasePool

from browser import StealthWindow
from hotkey import get_manager
from menu import StatusBarController
from config import load_config, save_config, hotkey_to_carbon, hotkey_display
from boss_manager import create_boss, get_active_boss, all_bosses
from launcher import LauncherController


class AppDelegate(NSObject):
    """应用代理"""

    def applicationDidFinishLaunching_(self, notification):
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self._config = load_config()
        self._toggle_hk_id = -1
        self._quit_hk_id = -1
        self._rearrange_hk_id = -1
        self._launcher_hk_id = -1
        self._boss = None
        self._window = None
        self._status_bar = None

        # 启动器
        self._launcher = LauncherController.alloc().initWithApp_(self)

        # 注册热键（先注册，启动器不影响）
        self._apply_hotkeys()

        NSLog("✓ Meowser 已启动")
        NSLog(f"  显示/隐藏: {hotkey_display(self._config['toggle_hotkey'])}")
        NSLog(f"  退出:     {hotkey_display(self._config['quit_hotkey'])}")
        NSLog(f"  整理:     {hotkey_display(self._config['rearrange_hotkey'])}")

        # 弹启动器（独立窗口）
        self._launcher.show()

    # ── 给 menu/launcher 用的桥接方法 ─────────────
    def config(self):
        return self._config

    @objc.typedSelector(b'v@:@')
    def applyConfig_(self, cfg):
        self._config = dict(cfg)
        save_config(self._config)
        self._apply_hotkeys()
        try:
            layout_cfg = self._config.get("layout", {})
            if self._boss is not None:
                self._boss.layout.set_edge(layout_cfg.get("edge", "left"))
                self._boss.layout.set_style(layout_cfg.get("style", "tile"))
                self._boss.layout.set_gap(layout_cfg.get("gap", 8))
                self._boss.layout.set_auto_reflow(layout_cfg.get("auto_reflow", True))
        except Exception as e:
            NSLog(f"applyConfig layout sync err: {e}")

    @objc.typedSelector(b'v@:@')
    def switchToProfile_(self, profile):
        """从启动器切换/初始化一个 Profile → 创建 Boss + 主窗口"""
        try:
            # 关闭旧 Boss 的所有窗口
            if self._boss is not None:
                try:
                    self._boss.close_all()
                except Exception:
                    pass
                self._boss = None

            # 把 profile 写到 config（这样 webview 启动时能拿到 proxy）
            self._config["profile"] = dict(profile)
            save_config(self._config)

            # 创建新 Boss
            self._boss = create_boss(
                profile_name=profile.get("name", "默认"),
                profile_cfg=profile,
            )

            # 应用 layout
            layout_cfg = self._config.get("layout", {})
            self._boss.layout.set_edge(layout_cfg.get("edge", "left"))
            self._boss.layout.set_style(layout_cfg.get("style", "tile"))
            self._boss.layout.set_gap(layout_cfg.get("gap", 8))
            self._boss.layout.set_auto_reflow(layout_cfg.get("auto_reflow", True))

            # 创建主窗口
            self._window = StealthWindow.alloc().initWithApp_(self)
            self._boss.set_main_window(self._window)
            self._window.makeKeyAndOrderFront_(None)

            # 创建/重设菜单栏
            if self._status_bar is None:
                self._status_bar = StatusBarController.alloc().initWithWindow_appDelegate_(
                    self._window, self
                )
            else:
                # 只重新绑定 _window
                self._status_bar._window = self._window
                self._status_bar.rebuild_menu()

            NSLog(f"✓ 切换到工作区: {profile.get('name')} · 模式: {profile.get('mode')} · 代理: {profile.get('proxy', {}).get('type', 'direct')}")
        except Exception as e:
            NSLog(f"switchToProfile_ err: {e}")
            import traceback
            NSLog(traceback.format_exc())

    def showLauncher(self):
        """供菜单栏调用：重新弹启动器（切换工作区）"""
        if self._launcher is not None:
            self._launcher.show()

    # ── 热键 ───────────────────────────────────
    def _apply_hotkeys(self):
        mgr = get_manager()
        for hk_id_attr in ["_toggle_hk_id", "_quit_hk_id", "_rearrange_hk_id", "_launcher_hk_id"]:
            old_id = getattr(self, hk_id_attr, -1)
            if old_id > 0:
                mgr.unregister(old_id)

        t_mods, t_code = hotkey_to_carbon(self._config["toggle_hotkey"])
        q_mods, q_code = hotkey_to_carbon(self._config["quit_hotkey"])
        r_mods, r_code = hotkey_to_carbon(self._config.get("rearrange_hotkey", {"modifiers": ["cmd", "alt"], "key": "R"}))
        l_mods, l_code = hotkey_to_carbon(self._config.get("launcher_hotkey", {"modifiers": ["cmd", "alt"], "key": "L"}))

        self._toggle_hk_id = mgr.register(
            t_mods, t_code, self._toggle_window,
            label=f"toggle {hotkey_display(self._config['toggle_hotkey'])}"
        )
        self._quit_hk_id = mgr.register(
            q_mods, q_code, self._quit_app,
            label=f"quit {hotkey_display(self._config['quit_hotkey'])}"
        )
        self._rearrange_hk_id = mgr.register(
            r_mods, r_code, self._rearrange,
            label=f"rearrange {hotkey_display(self._config.get('rearrange_hotkey', {}))}"
        )
        self._launcher_hk_id = mgr.register(
            l_mods, l_code, self.showLauncher,
            label=f"launcher {hotkey_display(self._config.get('launcher_hotkey', {'modifiers':['cmd','alt'], 'key':'L'}))}"
        )

    def _toggle_window(self):
        from AppKit import NSApplication
        app = NSApplication.sharedApplication()
        if self._boss is None or self._window is None:
            # 未选 profile 时，唤起启动器
            self.showLauncher()
            return
        # 同步隐藏/显示所有窗口
        any_visible = any(w.isVisible() for w in self._boss.all_windows())
        if any_visible:
            for w in self._boss.all_windows():
                if w.isVisible():
                    w.orderOut_(None)
        else:
            for w in self._boss.all_windows():
                w.makeKeyAndOrderFront_(None)
            app.activateIgnoringOtherApps_(True)

    def _rearrange(self):
        try:
            if self._boss is not None:
                self._boss.layout.reflow()
                NSLog("✓ 一键整理已触发")
        except Exception as e:
            NSLog(f"_rearrange err: {e}")

    def _quit_app(self):
        NSApplication.sharedApplication().terminate_(None)


def main():
    pool = NSAutoreleasePool.alloc().init()
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
    del pool


if __name__ == "__main__":
    main()
