"""
py2app 打包配置 — 生成 Meowser.app
用法: python setup.py py2app
"""

from setuptools import setup

APP = ["main.py"]
DATA_FILES = [
    ("", [
        "resources/home.html",
        "resources/menubar_kitten@1x.png",
        "resources/menubar_kitten@2x.png",
    ]),
]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "resources/MeowserIcon.icns",
    "resources": [
        "resources/home.html",
        "resources/menubar_kitten@1x.png",
        "resources/menubar_kitten@2x.png",
    ],
    "plist": {
        "CFBundleName": "Meowser",
        "CFBundleDisplayName": "Meowser",
        "CFBundleIdentifier": "com.meowser.app",
        "CFBundleVersion": "2.1.0",
        "CFBundleShortVersionString": "2.1.0",
        "LSUIElement": True,  # 菜单栏 App，不占 Dock
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "LSArchitecturePriority": ["arm64", "x86_64"],
        # ─── App Transport Security：允许内网 HTTP / 自签证书 ───
        "NSAppTransportSecurity": {
            # 仅放开 WebView 内的请求（NSURLSession 默认仍走 ATS）
            "NSAllowsArbitraryLoadsInWebContent": True,
            # 允许 HTTP（如内网 IP 没 HTTPS）
            "NSAllowsArbitraryLoads": True,
            # 内网 .local / IP 直连
            "NSAllowsLocalNetworking": True,
        },
        # 让 webview 主动声明本地网络可用（macOS 15+）
        "NSLocalNetworkUsageDescription": "Meowser 需要访问本地网络以加载内网链接（书签里的 IP 地址）",
    },
    "packages": ["objc", "AppKit", "Foundation", "WebKit", "Quartz"],
    "includes": ["browser", "hotkey", "menu", "config", "layout_manager", "boss_manager", "proxy", "profiles", "launcher", "edit_window", "bookmarks", "onepass"],
}

setup(
    name="Meowser",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
