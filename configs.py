# -*- coding: utf-8 -*-
"""工作流配置库：exe 同级的 config/ 文件夹，每个 .json 是一套工作流。

纯指针模型：settings["active_config"] 指向当前生效的 json 文件名，
井盖启动、编辑、保存都作用于这一个文件。

- default.json / latest.json 是两个受保护的固定槽：删除键只清空列表、不删文件。
- latest.json 专门放「暂存的当前桌面窗口」，每次暂存覆盖。
- 首次运行把旧 settings["workflow"] 迁进 default.json。
- 读写 UTF-8 + ensure_ascii=False，中文文件名与中文内容都支持。
"""

import os
import sys
import json

DEFAULT_NAME = "default.json"
LATEST_NAME = "latest.json"
PROTECTED = (DEFAULT_NAME, LATEST_NAME)


def configs_dir():
    """config/ 目录：打包后取 exe 同级，开发时取项目根目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config")


def _path(name):
    return os.path.join(configs_dir(), name)


def _ensure_dir():
    os.makedirs(configs_dir(), exist_ok=True)


def is_writable():
    """探测 config/ 能否写入（exe 放在无写权限目录时用于提示）。"""
    try:
        _ensure_dir()
        probe = _path(".__wtest")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


def ensure_ready(old_workflow):
    """首次运行：建 config/ 并把旧的 settings.workflow 迁进 default.json。
    default.json 已存在则不动。返回是否发生了迁移。"""
    _ensure_dir()
    if not os.path.exists(_path(DEFAULT_NAME)):
        save_config(DEFAULT_NAME, list(old_workflow or []))
        return True
    return False


def load_config(name):
    """读一个配置的 items 列表。不存在 / 损坏 / 格式不对都返回 []。"""
    try:
        with open(_path(name), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        items = data.get("items", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []
    return [i for i in items if isinstance(i, dict)]


def save_config(name, items):
    """原子写入一个配置。返回 True 表示成功（失败通常是没写权限）。"""
    try:
        _ensure_dir()
        path = _path(name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": list(items or [])}, f,
                      ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def delete_config(name):
    """删除一个配置。default/latest 只清空列表、保留文件。
    返回删除后应切到的配置名（受保护槽返回自身，其它返回 default）。"""
    if name in PROTECTED:
        save_config(name, [])
        return name
    try:
        os.remove(_path(name))
    except OSError:
        pass
    return DEFAULT_NAME


def list_configs():
    """下拉框顺序：latest（有内容时）→ default → 其它（按名排序）。
    latest 为空则 default 置顶。default/latest 始终出现。"""
    _ensure_dir()
    try:
        files = [fn for fn in os.listdir(configs_dir())
                 if fn.lower().endswith(".json")]
    except OSError:
        files = []
    others = sorted(f for f in files if f not in PROTECTED)
    if load_config(LATEST_NAME):
        ordered = [LATEST_NAME, DEFAULT_NAME]
    else:
        ordered = [DEFAULT_NAME, LATEST_NAME]
    ordered += others
    return ordered


def normalize_name(name):
    """把用户输入规范成合法的 xxx.json 文件名（去掉非法字符，保留中文）。"""
    name = (name or "").strip()
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    if not name:
        name = "工作流"
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


def unique_name(name):
    """若同名已存在，追加 _2 / _3 … 直到不冲突。"""
    if not os.path.exists(_path(name)):
        return name
    stem, ext = os.path.splitext(name)
    i = 2
    while os.path.exists(_path(f"{stem}_{i}{ext}")):
        i += 1
    return f"{stem}_{i}{ext}"


def import_config(external_path):
    """把外部 json 复制进 config/，沿用其文件名（重名自动加序号）。
    返回 (ok, 配置名或错误消息)。"""
    if not os.path.isfile(external_path):
        return False, "文件不存在"
    try:
        with open(external_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return False, f"读取失败：{e}"
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return False, "不是有效的工作流配置（缺少 items 列表）"
    base = os.path.basename(external_path)
    if not base.lower().endswith(".json"):
        base += ".json"
    name = unique_name(base)
    if save_config(name, [i for i in items if isinstance(i, dict)]):
        return True, name
    return False, "写入失败（config 目录可能没有写权限）"


def display_label(name):
    """下拉框里显示的名字。"""
    if name == LATEST_NAME:
        return f"{LATEST_NAME}（临时）"
    return name
