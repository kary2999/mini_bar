#!/usr/bin/env bash
#
# Meowser 一键打包脚本
# 产物：dist/Meowser-vX.Y.Z.zip (内含 Meowser.app + 打开.command + 使用说明.txt)
#

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ── Python 解释器 ─────────────────────────────────────
if [ -x "$HOME/.rysc-venv/bin/python3" ]; then
    PYBIN="$HOME/.rysc-venv/bin/python3"
elif [ -x "$(which python3)" ]; then
    PYBIN="python3"
else
    echo "❌ 找不到 python3"
    exit 1
fi

APP_NAME="Meowser"

# 从 setup.py 读版本号
VERSION=$("$PYBIN" -c "
import re
with open('setup.py') as f:
    m = re.search(r'CFBundleShortVersionString[\"\\']?\s*:\s*[\"\\']([^\"\\']+)', f.read())
print(m.group(1) if m else '0.0.0')
")

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ${APP_NAME} v${VERSION} 打包流程"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 步骤 1: 清理 ────────────────────────────────────
echo ""
echo "▶ [1/5] 清理旧产物..."
rm -rf build dist

# ── 步骤 2: 检查依赖 ────────────────────────────────
echo ""
echo "▶ [2/5] 检查依赖..."
"$PYBIN" -c "import objc; import AppKit; import WebKit; print('  ✓ PyObjC 就绪')" || {
    echo "  安装 PyObjC..."
    "$PYBIN" -m pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit pyobjc-framework-Quartz
}

# ── 步骤 3: py2app 构建 ────────────────────────────
echo ""
echo "▶ [3/5] py2app 构建..."
"$PYBIN" setup.py py2app 2>&1 | tail -5

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "❌ 构建失败"
    exit 1
fi

# ── 步骤 4: 签名 ───────────────────────────────────
echo ""
echo "▶ [4/5] Ad-hoc 签名..."

ENTITLEMENTS="$(mktemp /tmp/meowser_ent.XXXXXX.plist)"
cat > "$ENTITLEMENTS" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key>
  <true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
  <true/>
  <key>com.apple.security.cs.disable-library-validation</key>
  <true/>
</dict>
</plist>
EOF

find "dist/${APP_NAME}.app/Contents" -name "*.so" -o -name "*.dylib" | while read lib; do
    codesign --force --sign - --options runtime --timestamp "$lib" 2>/dev/null || true
done

codesign --force --sign - --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --timestamp \
    "dist/${APP_NAME}.app" 2>&1 | head -5 || true

rm -f "$ENTITLEMENTS"

# ── 步骤 5: 打 zip（内含 app + 一键打开脚本 + 说明）──────
echo ""
echo "▶ [5/5] 生成分发 zip..."

RELEASE_DIR="dist/${APP_NAME}-v${VERSION}"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# 复制 app
cp -R "dist/${APP_NAME}.app" "$RELEASE_DIR/"

# 写入"打开.command" —— 双击即解除 Gatekeeper 并启动
cat > "$RELEASE_DIR/打开.command" <<'OPEN_EOF'
#!/usr/bin/env bash
#
# Meowser — 一键打开
# 自动解除 macOS "无法验证开发者" 警告并启动 App
#

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/Meowser.app"

if [ ! -d "$APP" ]; then
    echo "❌ 找不到 Meowser.app，请确保本脚本和 Meowser.app 在同一文件夹"
    read -p "按回车键关闭..."
    exit 1
fi

echo "→ 解除 Gatekeeper 限制..."
xattr -cr "$APP" 2>/dev/null || true

echo "→ 启动 Meowser..."
open "$APP"

echo ""
echo "✅ 完成。菜单栏右上角有个小黑点 ●，那就是 Meowser。"
echo "   快捷键 ⌘⌥B 可随时显示/隐藏浏览器窗口。"
echo ""
sleep 2
OPEN_EOF
chmod +x "$RELEASE_DIR/打开.command"

# 使用说明
cat > "$RELEASE_DIR/使用说明.txt" <<'README_EOF'
Meowser — 浮动小浏览器

【首次使用】
方式 A（推荐）：双击本文件夹里的「打开.command」
方式 B：右键点 Meowser.app → "打开" → 在弹窗里再次点"打开"
方式 C：拖入 /Applications 后，在终端运行:
       xattr -cr "/Applications/Meowser.app"

【操作】
• 菜单栏右上角会出现小黑点 ● ，点它有菜单
• 屏幕右下角出现 200×150 小浏览器（默认 YouTube）
• 双击小窗 → 放大到 1200×800
• 放大状态下点击窗口外 → 自动缩回小窗
• 大窗地址栏右侧有透明度滑块，可实时调整
• ⌘⌥B = 显示 / 隐藏（全局有效，不用授权）

【系统要求】
• macOS 11 (Big Sur) 或更新
• Apple Silicon（M1/M2/M3/M4/M5）
• 暂不支持 Intel Mac
README_EOF

# 打包（用 zip 而非 ditto，彻底避免 ._AppleDouble 元数据）
ZIP_PATH="dist/${APP_NAME}-v${VERSION}.zip"
rm -f "$ZIP_PATH"
find "$RELEASE_DIR" -name "._*" -delete 2>/dev/null || true
xattr -cr "$RELEASE_DIR" 2>/dev/null || true
cd dist
COPYFILE_DISABLE=1 zip -qry --symlinks "${APP_NAME}-v${VERSION}.zip" "${APP_NAME}-v${VERSION}" -x "*.DS_Store" -x "*/._*"
cd ..

# 清理中间目录（保留 app 和 zip）
rm -rf "$RELEASE_DIR"

SIZE=$(du -h "$ZIP_PATH" | cut -f1)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 打包完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  📦 分发 zip: $ZIP_PATH  (${SIZE})"
echo "  📱 开发测试: dist/${APP_NAME}.app"
echo ""
echo "  【分发给朋友】"
echo "    1. 发送 $ZIP_PATH"
echo "    2. 对方解压 → 双击【打开.command】→ 完成"
echo ""
echo "  【系统要求】"
echo "    • macOS 11+ / Apple Silicon (M 系列)"
echo ""
