# -*- coding: utf-8 -*-
"""工作流：依次启动一组程序，并按记录的位置/尺寸还原窗口。"""

import os
import time
import threading
import subprocess

import winapi


def _restore_new_window(match_path, before, item, name, progress):
    """等按 match_path 的 exe 出现的新窗口，再把它摆到记录的位置尺寸。"""
    hwnd = None
    for _ in range(60):
        time.sleep(0.2)
        hwnd = winapi.find_window_by_exe(match_path, exclude=before)
        if hwnd:
            break
    if hwnd:
        time.sleep(0.4)  # 让窗口初始化完，避免被程序自身覆盖位置
        ok = winapi.set_window_rect(
            hwnd, item["x"], item["y"], item["w"], item["h"],
            maximized=item.get("maximized", False))
        if progress:
            progress(f"已还原窗口：{name}" if ok else f"未能还原窗口：{name}")
    elif progress:
        progress(f"未找到窗口，跳过还原：{name}")


def _launch_one(item, progress=None):
    """启动单个工作流项。按 type 分 app / browser / explorer 三类。"""
    itype = item.get("type", "app")
    path = item.get("path", "")
    name = item.get("name") or (os.path.basename(path) if path else itype)

    # 兜底跳过井盖自身（历史 latest.json 里可能残留井盖条目）
    if path and os.path.basename(path).lower() == winapi.own_exe_basename():
        if progress:
            progress(f"跳过井盖自身：{name}")
        return

    if itype == "explorer":
        folder = item.get("folder", "")
        if not folder or not os.path.isdir(folder):
            if progress:
                progress(f"跳过（文件夹不存在）：{name}")
            return
        if progress:
            progress(f"打开文件夹：{name}")
        before = winapi.snapshot_hwnds()
        try:
            subprocess.Popen(["explorer.exe", folder])
        except OSError as e:
            if progress:
                progress(f"打开失败：{name}（{e}）")
            return
        if item.get("restore"):
            _restore_new_window("explorer.exe", before, item, name, progress)
        return

    # browser / app 都是启动 path 指向的可执行文件
    if not path or not os.path.exists(path):
        if progress:
            progress(f"跳过（找不到）：{name}")
        return

    if itype == "browser":
        url = item.get("url", "")
        cmd = [path, "--new-window", url] if url else [path]
        if progress:
            progress(f"打开浏览器：{name}")
    else:
        cmd = [path] + list(item.get("args", []))
        if progress:
            progress(f"启动：{name}")

    before = winapi.snapshot_hwnds()
    try:
        subprocess.Popen(cmd, cwd=os.path.dirname(path) or None)
    except OSError as e:
        if progress:
            progress(f"启动失败：{name}（{e}）")
        return

    if item.get("restore"):
        _restore_new_window(path, before, item, name, progress)


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
