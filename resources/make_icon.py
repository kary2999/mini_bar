#!/usr/bin/env python3
"""
生成透明背景小星星图标 (1024x1024 PNG)
无需 Pillow，直接用 PyObjC 画图
"""

from AppKit import (
    NSImage, NSBitmapImageRep, NSColor, NSBezierPath,
    NSGraphicsContext, NSPNGFileType,
)
from Foundation import NSURL
import math, os

SIZE = 1024


def make_star_path(cx, cy, r_outer, r_inner, points=5):
    """5 角星路径"""
    path = NSBezierPath.bezierPath()
    angle = -math.pi / 2  # 顶点朝上
    step = math.pi / points
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        if i == 0:
            path.moveToPoint_((x, y))
        else:
            path.lineToPoint_((x, y))
        angle += step
    path.closePath()
    return path


def make_png(size, out_path):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0
    )
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)

    # 透明背景 (什么都不画即可)

    # 金黄色小星星
    cx = size / 2
    cy = size / 2
    r_outer = size * 0.42
    r_inner = r_outer * 0.4
    star = make_star_path(cx, cy, r_outer, r_inner)

    # 填充渐变金色
    NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.82, 0.17, 1.0).setFill()
    star.fill()

    # 深色描边
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.55, 0.40, 0.05, 1.0).setStroke()
    star.setLineWidth_(size * 0.015)
    star.stroke()

    NSGraphicsContext.restoreGraphicsState()

    data = rep.representationUsingType_properties_(NSPNGFileType, None)
    data.writeToFile_atomically_(out_path, True)
    print(f"✓ 生成: {out_path}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    # 生成多尺寸 iconset
    iconset = os.path.join(here, "MeowserIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for size, name in [
        (16,   "icon_16x16.png"),
        (32,   "icon_16x16@2x.png"),
        (32,   "icon_32x32.png"),
        (64,   "icon_32x32@2x.png"),
        (128,  "icon_128x128.png"),
        (256,  "icon_128x128@2x.png"),
        (256,  "icon_256x256.png"),
        (512,  "icon_256x256@2x.png"),
        (512,  "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]:
        make_png(size, os.path.join(iconset, name))
    print(f"✓ iconset 目录就绪: {iconset}")
