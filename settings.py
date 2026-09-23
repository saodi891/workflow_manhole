# -*- coding: utf-8 -*-
"""设置持久化：把工作流、行为模式、风格、置顶等存成 JSON。

存放位置：%APPDATA%\\井盖桌宠\\settings.json
（打包成 exe 后也能正常读写，不受 onefile 临时目录影响）
"""

import os
import sys
import json

import config

APP_NAME = "井盖桌宠"


def data_dir():
    """可写的数据目录（存设置、日志）。"""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def settings_path():
    return os.path.join(data_dir(), "settings.json")


DEFAULTS = {
    "on_top": bool(config.ALWAYS_ON_TOP),
    "behavior": "idle",     # idle=待机不动（默认） / wander=散步
    "gravity": False,        # 默认无重力；无重力时可趴在屏幕两侧墙壁上
    "style_path": "",        # 风格包路径（.zip 或文件夹）；空=默认井盖
    "workflow": [],          # 旧版工作流；v0.3 起仅作首次迁移源，实际存 config/*.json
    "active_config": "default.json",  # 当前生效的工作流配置文件名（config/ 下）
}


def load():
    """读取设置，缺字段用默认值补齐。读失败则返回默认。"""
    result = dict(DEFAULTS)
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in DEFAULTS:
                if k in data:
                    result[k] = data[k]
    except (OSError, ValueError):
        pass
    # 轻量校验
    if result["behavior"] not in ("wander", "idle"):
        result["behavior"] = "wander"
    if not isinstance(result["workflow"], list):
        result["workflow"] = []
    if not isinstance(result.get("active_config"), str) or not result["active_config"]:
        result["active_config"] = "default.json"
    return result


def save(data):
    """原子写入，避免写一半损坏文件。"""
    path = settings_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def new_workflow_item(name="", path="", args=None, restore=False,
                      x=0, y=0, w=0, h=0, maximized=False):
    return {
        "name": name or (os.path.basename(path) if path else "程序"),
        "path": path,
        "args": list(args or []),
        "restore": bool(restore),
        "x": int(x), "y": int(y), "w": int(w), "h": int(h),
        "maximized": bool(maximized),
    }
