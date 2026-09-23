# -*- coding: utf-8 -*-
"""工作流：依次启动一组程序，并按记录的位置/尺寸还原窗口。"""

import os
import time
import threading
import subprocess

import winapi


def _launch_one(item, progress=None):
    """启动单个程序，如需还原窗口则等它出现后 SetWindowPos。"""
    path = item.get("path", "")
    if not path or not os.path.exists(path):
        if progress:
            progress(f"跳过（找不到）：{item.get('name') or path}")
        return

    name = item.get("name") or os.path.basename(path)
    if progress:
        progress(f"启动：{name}")

    before = winapi.snapshot_hwnds()
    try:
        subprocess.Popen(
            [path] + list(item.get("args", [])),
            cwd=os.path.dirname(path) or None,
        )
    except OSError as e:
        if progress:
            progress(f"启动失败：{name}（{e}）")
        return

    if not item.get("restore"):
        return

    # 等新窗口出现（最多约 12 秒），再还原它的位置和尺寸
    hwnd = None
    for _ in range(60):
        time.sleep(0.2)
        hwnd = winapi.find_window_by_exe(path, exclude=before)
        if hwnd:
            break
    if hwnd:
        # 再稍等一下让窗口初始化完成，避免被程序自身覆盖位置
        time.sleep(0.4)
        ok = winapi.set_window_rect(
            hwnd, item["x"], item["y"], item["w"], item["h"],
            maximized=item.get("maximized", False))
        if progress:
            progress(f"已还原窗口：{name}" if ok else f"未能还原窗口：{name}")
    elif progress:
        progress(f"未找到窗口，跳过还原：{name}")


def run(items, gap_seconds=0.8, progress=None, done=None):
    """在后台线程依次启动 items。progress(str)/done() 回调用于 UI 反馈。"""
    def worker():
        for item in items:
            _launch_one(item, progress)
            time.sleep(gap_seconds)
        if progress:
            progress("工作流启动完成")
        if done:
            done()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
