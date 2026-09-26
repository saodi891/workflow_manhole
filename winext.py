# -*- coding: utf-8 -*-
"""Windows COM 扩展：读浏览器活动标签 URL、资源管理器文件夹路径。

与纯 ctypes 的 winapi.py 分开：这里依赖 pywin32 + uiautomation（打包进 exe）。
任一依赖缺失或非 Windows 平台，所有函数安全降级为空结果，绝不抛异常。
"""

import sys
import os

IS_WINDOWS = sys.platform == "win32"

BROWSER_EXES = {"msedge.exe", "chrome.exe"}

try:
    import pythoncom
    import win32com.client
    _HAS_SHELL = IS_WINDOWS
except Exception:
    _HAS_SHELL = False

try:
    import uiautomation as _auto
    _HAS_UIA = IS_WINDOWS
except Exception:
    _HAS_UIA = False


def _file_url_to_path(url):
    """file:///E:/a/b -> E:\\a\\b；非 file:// 或解析失败返回 ""。"""
    if not url or not url.lower().startswith("file:"):
        return ""
    try:
        import urllib.parse
        import urllib.request
        p = urllib.request.url2pathname(urllib.parse.urlparse(url).path)
        return p
    except Exception:
        return ""


def explorer_folders():
    """返回 {hwnd: 文件夹本地路径}，只含真正的文件资源管理器窗口。
    特殊页（此电脑 / 快速访问 / 控制面板，LocationURL 为空或非 file://）跳过。"""
    if not _HAS_SHELL:
        return {}
    result = {}
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        wins = shell.Windows()
        for i in range(wins.Count):
            w = wins.Item(i)
            if w is None:
                continue
            try:
                full = (w.FullName or "").lower()
                if not full.endswith("explorer.exe"):
                    continue  # IE / 其它 Shell 窗口不算资源管理器
                path = _file_url_to_path(w.LocationURL or "")
                if not path:
                    continue
                result[int(w.HWND)] = path
            except Exception:
                continue
    except Exception:
        return {}
    finally:
        pythoncom.CoUninitialize()
    return result


def browser_active_url(hwnd):
    """读一个浏览器窗口当前活动标签的 URL（经 UI Automation 读地址栏）。
    读不到返回 ""。地址栏常不带 scheme，补 https://。"""
    if not _HAS_UIA or not hwnd:
        return ""
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        win = _auto.ControlFromHandle(int(hwnd))
        if not win:
            return ""
        edit = win.EditControl(searchDepth=20)
        if not edit or not edit.Exists(0, 0):
            return ""
        val = ""
        try:
            val = edit.GetValuePattern().Value or ""
        except Exception:
            val = getattr(edit, "Name", "") or ""
        val = val.strip()
        if not val:
            return ""
        low = val.lower()
        if low.startswith(("http://", "https://", "file:", "edge:", "chrome:", "about:")):
            return val
        return "https://" + val
    except Exception:
        return ""
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def classify(exe_basename, hwnd, folder_map):
    """按 exe 文件名 + 是否命中资源管理器映射，判定窗口类型。"""
    b = (exe_basename or "").lower()
    if b in BROWSER_EXES:
        return "browser"
    if b == "explorer.exe" and int(hwnd) in folder_map:
        return "explorer"
    return "app"
