# -*- coding: utf-8 -*-
"""加载帧序列。找不到图时生成一个井盖占位图，保证程序能直接跑。"""

import os
import sys
import math
import zipfile

from PySide6.QtCore import Qt, QRectF, QBuffer, QByteArray
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPen, QRadialGradient, QImageReader,
)

import config


def _resource_base():
    """打包成 exe 后资源会被解压到临时目录，用 _MEIPASS 定位；否则用脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _load_folder(folder, size):
    """按文件名排序加载一个文件夹里的所有帧，缩放到 size×size。"""
    folder = os.path.join(_resource_base(), folder)
    if not os.path.isdir(folder):
        return []
    names = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith(config.IMAGE_EXTS)
    )
    frames = []
    for name in names:
        pix = QPixmap(os.path.join(folder, name))
        if pix.isNull():
            continue
        frames.append(pix.scaled(
            size, size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        ))
    return frames


def _placeholder_manhole(size, shade=0):
    """程序化画一个井盖当占位图。shade 让不同状态略有区别，方便肉眼分辨。"""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    cx = cy = size / 2
    r = size * 0.44

    # 铁灰色径向渐变，做出金属质感
    grad = QRadialGradient(cx, cy - r * 0.2, r)
    base = 90 + shade
    grad.setColorAt(0.0, QColor(base + 40, base + 40, base + 45))
    grad.setColorAt(1.0, QColor(max(0, base - 40), max(0, base - 40), max(0, base - 35)))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(QColor(40, 40, 45), max(2, size // 40)))
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

    # 一圈螺栓
    p.setBrush(QColor(60, 60, 65))
    p.setPen(Qt.NoPen)
    bolts, br = 12, r * 0.9
    for i in range(bolts):
        a = 2 * math.pi * i / bolts
        bx = cx + br * math.cos(a)
        by = cy + br * math.sin(a)
        p.drawEllipse(QRectF(bx - r * 0.05, by - r * 0.05, r * 0.1, r * 0.1))

    # 中间的花纹格子
    p.setPen(QPen(QColor(50, 50, 55), max(1, size // 64)))
    step = r / 3
    for gx in range(-2, 3):
        p.drawLine(int(cx + gx * step), int(cy - r * 0.6),
                   int(cx + gx * step), int(cy + r * 0.6))
    for gy in range(-2, 3):
        p.drawLine(int(cx - r * 0.6), int(cy + gy * step),
                   int(cx + r * 0.6), int(cy + gy * step))

    # 一双简单的眼睛，让它有“宠物感”
    eye_r = r * 0.14
    ey = cy - r * 0.15
    for ex in (cx - r * 0.35, cx + r * 0.35):
        p.setBrush(QColor(245, 245, 245))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(ex - eye_r, ey - eye_r, eye_r * 2, eye_r * 2))
        p.setBrush(QColor(20, 20, 20))
        p.drawEllipse(QRectF(ex - eye_r * 0.45, ey - eye_r * 0.45,
                             eye_r * 0.9, eye_r * 0.9))

    p.end()
    return pix


def _frames_from_reader(reader, size):
    """从 QImageReader 逐帧读取（支持动图 gif），缩放到 size×size。"""
    frames = []
    while True:
        img = reader.read()
        if img.isNull():
            break
        frames.append(QPixmap.fromImage(img).scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation,
        ))
        if reader.imageCount() <= 1:
            break  # 单帧图，读一次就够
    return frames


def _gif_from_file(path, size):
    reader = QImageReader(path)
    return _frames_from_reader(reader, size)


def _gif_from_bytes(data, size):
    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QBuffer.ReadOnly)
    reader = QImageReader(buf)
    frames = _frames_from_reader(reader, size)
    buf.close()
    return frames


def load_style_pack(path, size):
    """从风格包读取各状态的同名 gif（idle.gif/walk.gif/...）。

    path 可以是一个文件夹，或一个 .zip。返回 {状态: [帧,...]}，
    只包含成功读到的状态；读不到的状态不在结果里（交给调用方回退）。
    """
    result = {}
    if not path:
        return result

    if os.path.isdir(path):
        for state in config.STATES:
            fp = os.path.join(path, state + ".gif")
            if os.path.isfile(fp):
                frames = _gif_from_file(fp, size)
                if frames:
                    result[state] = frames

    elif os.path.isfile(path) and path.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as z:
                # 允许 gif 放在 zip 根目录或任意子目录，按 basename 匹配
                by_base = {}
                for n in z.namelist():
                    by_base.setdefault(os.path.basename(n).lower(), n)
                for state in config.STATES:
                    key = state + ".gif"
                    if key in by_base:
                        frames = _gif_from_bytes(z.read(by_base[key]), size)
                        if frames:
                            result[state] = frames
        except (zipfile.BadZipFile, OSError):
            pass

    return result


def load_states(size, style_path=""):
    """返回 {状态名: [帧,...]}。

    优先级：风格包 gif > assets 下的 png 帧文件夹 > 内置井盖占位图。
    """
    result = {}
    shades = {"idle": 0, "walk": 10, "drag": -10, "sleep": -25, "click": 25, "wait": 15}
    style = load_style_pack(style_path, size)
    for state, folder in config.STATES.items():
        frames = style.get(state) or _load_folder(folder, size)
        if not frames:
            frames = [_placeholder_manhole(size, shades.get(state, 0))]
        result[state] = frames
    return result
