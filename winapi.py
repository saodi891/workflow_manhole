# -*- coding: utf-8 -*-
"""Windows 窗口工具（纯 ctypes，无需额外依赖）。

用于工作流功能：枚举当前打开的窗口、记录/恢复窗口的位置和尺寸。
非 Windows 平台上所有函数安全降级为“空操作”。
"""

import os
import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SW_SHOWNORMAL = 1
    SW_MAXIMIZE = 3
    SW_RESTORE = 9

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.UINT),
            ("flags", wintypes.UINT),
            ("showCmd", wintypes.UINT),
            ("ptMinPosition", _POINT),
            ("ptMaxPosition", _POINT),
            ("rcNormalPosition", wintypes.RECT),
        ]

    user32.GetWindowPlacement.argtypes = [
        wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)
    ]

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
    ]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND

    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]


def _exe_for_pid(pid):
    if not IS_WINDOWS or not pid:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(h)
    return ""


def _window_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _pid_for_hwnd(hwnd):
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _rect_for_hwnd(hwnd):
    r = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)
    return (0, 0, 0, 0)


def _placement_for_hwnd(hwnd):
    """用 GetWindowPlacement 取「还原态」的位置尺寸 + 是否最大化。

    比 GetWindowRect 可靠：最小化/最大化的窗口也能拿到正常还原坐标，
    不会出现 -32000 那种离屏垃圾值。返回 (x, y, w, h, maximized) 或 None。
    """
    wp = _WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(_WINDOWPLACEMENT)
    if not user32.GetWindowPlacement(hwnd, ctypes.byref(wp)):
        return None
    r = wp.rcNormalPosition
    x, y, w, h = r.left, r.top, r.right - r.left, r.bottom - r.top
    # -32000 那类离屏哨兵值在高 DPI 进程里会被缩放（如 ÷1.5≈-21333），
    # 所以用 -20000 兜底：没有正常窗口会停在离屏两万像素外。
    if w <= 0 or h <= 0 or x < -20000 or y < -20000:
        return None  # 从未正常显示过的窗口，坐标不可信
    return (x, y, w, h, wp.showCmd == SW_MAXIMIZE)


def list_windows():
    """返回当前可见、有标题、且是顶层的窗口列表。

    每项：{hwnd, title, pid, exe, x, y, w, h}
    """
    if not IS_WINDOWS:
        return []
    results = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetParent(hwnd):  # 只要顶层窗口
            return True
        title = _window_title(hwnd)
        if not title:
            return True
        pid = _pid_for_hwnd(hwnd)
        # 用 GetWindowPlacement 的还原坐标（最小化/最大化也可靠）；
        # 拿不到可信坐标（离屏/从未显示）就跳过，避免记录垃圾位置。
        pl = _placement_for_hwnd(hwnd)
        if pl is None:
            return True
        x, y, w, h, maximized = pl
        results.append({
            "hwnd": hwnd, "title": title, "pid": pid,
            "exe": _exe_for_pid(pid), "x": x, "y": y, "w": w, "h": h,
            "maximized": maximized,
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return results


def snapshot_hwnds():
    """当前所有顶层窗口 hwnd 的集合，用于启动前后做差集找新窗口。"""
    return {w["hwnd"] for w in list_windows()}


def find_window_by_exe(exe_path, exclude=None):
    """按 exe 文件名找窗口 hwnd，可排除已存在的一批 hwnd。找不到返回 None。"""
    if not IS_WINDOWS or not exe_path:
        return None
    exclude = exclude or set()
    target = os.path.basename(exe_path).lower()
    for w in list_windows():
        if w["hwnd"] in exclude:
            continue
        if w["exe"] and os.path.basename(w["exe"]).lower() == target:
            return w["hwnd"]
    return None


def set_window_rect(hwnd, x, y, w, h, maximized=False):
    """把窗口移动到 (x,y) 并调整为 w×h。先还原（避免最小化/最大化）。
    maximized=True 时：先摆好还原态坐标，再最大化，这样取消最大化能回到该位置。"""
    if not IS_WINDOWS or not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    ok = bool(user32.SetWindowPos(
        hwnd, 0, int(x), int(y), int(w), int(h),
        SWP_NOZORDER | SWP_NOACTIVATE,
    ))
    if maximized:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
    return ok
