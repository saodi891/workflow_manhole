# -*- coding: utf-8 -*-
"""程序化生成像素风「井盖」动画帧。

概念：扁平圆盘井盖 + 井字纹 + 两只可爱大眼 + 底部小短腿。铁灰色。
输出：assets/<状态>/001..004.png，64×64，透明背景。
运行：python scripts/gen_pixel_art.py
依赖：Pillow
"""

import os
import math
from PIL import Image, ImageDraw

GRID = 32          # 逻辑像素网格
SCALE = 2          # 放大到 64×64
SIZE = GRID * SCALE
FRAMES = 4

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# ---- 铁灰调色板 ----
T = (0, 0, 0, 0)
DISK_HI = (150, 154, 164, 255)   # 盘面高光
DISK = (118, 122, 132, 255)      # 盘面主色
DISK_DK = (92, 96, 105, 255)     # 盘面暗部
RIM = (60, 63, 70, 255)          # 外圈厚边
EDGE = (34, 35, 40, 255)         # 描边
GROOVE = (72, 75, 84, 255)       # 井字纹凹槽
LEG = (44, 46, 52, 255)          # 腿
FOOT = (34, 35, 40, 255)         # 脚
EYE_W = (245, 247, 250, 255)     # 眼白
EYE_D = (26, 26, 30, 255)        # 瞳孔
EYE_HI = (255, 255, 255, 255)    # 眼高光
ZZZ = (200, 220, 255, 255)
STAR = (255, 232, 140, 255)


def _canvas():
    return Image.new("RGBA", (GRID, GRID), T)


def _px(d, x, y, color):
    xi, yi = int(round(x)), int(round(y))
    if 0 <= xi < GRID and 0 <= yi < GRID:
        d.point((xi, yi), fill=color)


def _disk(d, cx, cy, r):
    """扁平圆盘：外圈厚边 + 盘面分层 + 井字纹 + 描边。"""
    r2 = r * r
    rim_in = (r - 2) ** 2
    for y in range(GRID):
        for x in range(GRID):
            dd = (x - cx) ** 2 + (y - cy) ** 2
            if dd > r2:
                continue
            if dd > rim_in:
                d.point((x, y), fill=RIM)            # 外圈厚边
            else:
                # 盘面：左上偏亮、右下偏暗，做一点体积
                grad = (x - cx) + (y - cy)
                if grad < -r * 0.5:
                    c = DISK_HI
                elif grad > r * 0.5:
                    c = DISK_DK
                else:
                    c = DISK
                d.point((x, y), fill=c)

    # 井字纹：两竖两横，只画在盘面内
    off = int(r * 0.42)
    for gx in (-off, off):
        for y in range(GRID):
            if (gx) ** 2 + (y - cy) ** 2 <= rim_in:
                _px(d, cx + gx, y, GROOVE)
    for gy in (-off, off):
        for x in range(GRID):
            if (x - cx) ** 2 + (gy) ** 2 <= rim_in:
                _px(d, x, cy + gy, GROOVE)

    # 描边
    for y in range(GRID):
        for x in range(GRID):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if (x + dx - cx) ** 2 + (y + dy - cy) ** 2 > r2:
                        d.point((x, y), fill=EDGE)
                        break


def _eyes(d, cx, cy, look=0, closed=False, happy=False):
    """两只可爱大眼：3×3 眼白 + 瞳孔 + 高光。"""
    sep = 5
    for sx in (-sep, sep):
        bx, by = cx + sx, cy
        if closed:
            for t in (-1, 0, 1):
                _px(d, bx + t, by, EYE_D)
            continue
        if happy:  # ^ ^ 弯眼
            _px(d, bx - 1, by + 1, EYE_D)
            _px(d, bx, by, EYE_D)
            _px(d, bx + 1, by + 1, EYE_D)
            continue
        # 3×3 眼白
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                _px(d, bx + ox, by + oy, EYE_W)
        # 瞳孔 2×2，随 look 偏移
        px = bx + (1 if look > 0 else (-1 if look < 0 else 0))
        for ox in (0, 1):
            for oy in (0, 1):
                _px(d, px + ox - (1 if look >= 0 else 0), by + oy - 1, EYE_D)
        _px(d, px, by - 1, EYE_HI)   # 高光点


def _legs(d, cx, cy, r, phase=0, amp=0, count=4, spread=0.7, splay=False):
    """底部伸出的小短腿。amp>0 时随 phase 迈步。"""
    base_y = cy + int(r * 0.72)
    for i in range(count):
        frac = (i - (count - 1) / 2) / max(1, (count - 1) / 2)
        lx = cx + int(frac * r * spread)
        step = math.sin(phase + i * 1.3)
        lift = int(amp * max(0, step))
        top = base_y - 1
        # 腿两节 + 脚
        _px(d, lx, top, LEG)
        if splay:
            _px(d, lx, top + 2 - lift, LEG)
            _px(d, lx + (1 if frac >= 0 else -1), top + 3 - lift, FOOT)
        else:
            _px(d, lx, top + 2 - lift, LEG)
            _px(d, lx, top + 3 - lift, FOOT)


def _save(img, state, idx):
    out_dir = os.path.join(ROOT, "assets", state)
    os.makedirs(out_dir, exist_ok=True)
    img.resize((SIZE, SIZE), Image.NEAREST).save(os.path.join(out_dir, f"{idx:03d}.png"))


# ---------- 各状态 ----------
def gen_idle():
    cx = GRID // 2
    for f in range(FRAMES):
        img = _canvas(); d = ImageDraw.Draw(img)
        bob = [0, -1, 0, 1][f]
        cy = 14 + bob
        _legs(d, cx, cy, 11, amp=0)
        _disk(d, cx, cy, 11)
        _eyes(d, cx, cy - 1, closed=(f == 2))
        _save(img, "idle", f + 1)


def gen_walk():
    cx = GRID // 2
    for f in range(FRAMES):
        img = _canvas(); d = ImageDraw.Draw(img)
        bob = [0, -1, 0, -1][f]
        cy = 14 + bob
        _legs(d, cx, cy, 11, phase=f * math.pi / 2, amp=3)
        _disk(d, cx, cy, 11)
        _eyes(d, cx, cy - 1, look=1)
        _save(img, "walk", f + 1)


def gen_drag():
    cx = GRID // 2
    for f in range(FRAMES):
        img = _canvas(); d = ImageDraw.Draw(img)
        sway = [-1, 1, -1, 1][f]
        cy = 13
        _legs(d, cx + sway, cy, 11, phase=f * 1.9, amp=4, splay=True)  # 腿乱蹬
        _disk(d, cx + sway, cy, 11)
        _eyes(d, cx + sway, cy - 1, look=sway)
        _save(img, "drag", f + 1)


def gen_sleep():
    cx = GRID // 2
    for f in range(FRAMES):
        img = _canvas(); d = ImageDraw.Draw(img)
        cy = 15
        _legs(d, cx, cy, 12, amp=0, spread=0.9, splay=True)   # 腿摊开趴着
        _disk(d, cx, cy, 12)
        _eyes(d, cx, cy - 1, closed=True)
        seq = [(8, 0), (10, -3), (12, -6)]
        for i, (zx, zy) in enumerate(seq):
            if i <= f - 1:
                _px(d, cx + zx, cy - 8 + zy, ZZZ)
                _px(d, cx + zx + 1, cy - 8 + zy, ZZZ)
                _px(d, cx + zx, cy - 7 + zy, ZZZ)
        _save(img, "sleep", f + 1)


def gen_click():
    cx = GRID // 2
    for f in range(FRAMES):
        img = _canvas(); d = ImageDraw.Draw(img)
        pop = [1, -2, -1, 0][f]
        cy = 14 + pop
        _legs(d, cx, cy, 11, phase=f * 2.0, amp=3 if f in (1, 2) else 0)  # 蹦跶
        _disk(d, cx, cy, 11)
        _eyes(d, cx, cy - 1, happy=(f in (1, 2)))
        if f in (1, 2):
            for sx, sy in ((-11, -6), (11, -7), (0, -12)):
                _px(d, cx + sx, cy + sy, STAR)
        _save(img, "click", f + 1)


def gen_wait():
    cx = GRID // 2
    for f in range(FRAMES):
        img = _canvas(); d = ImageDraw.Draw(img)
        cy = 14
        _legs(d, cx, cy, 11, amp=0)
        _disk(d, cx, cy, 11)
        _eyes(d, cx, cy - 1, look=[-1, -1, 1, 1][f])   # 左右张望
        a = 2 * math.pi * f / FRAMES
        _px(d, cx + int(9 * math.cos(a)), cy - 12 + int(3 * math.sin(a)), STAR)
        _save(img, "wait", f + 1)


def main():
    gen_idle(); gen_walk(); gen_drag(); gen_sleep(); gen_click(); gen_wait()
    print("像素帧已生成到 assets/<状态>/001..004.png（64×64）")


if __name__ == "__main__":
    main()
