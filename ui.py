# -*- coding: utf-8 -*-
"""设置窗口：工作流、风格、行为模式、窗口置顶。

对 pet 的改动通过传入的 pet 实例的 apply_* 方法即时生效并持久化。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QRadioButton, QButtonGroup,
    QCheckBox, QFileDialog, QLineEdit, QSpinBox, QMessageBox, QFormLayout,
    QDialogButtonBox, QGroupBox, QComboBox, QInputDialog,
)

import settings as settings_mod
import wf_runner
import winapi
import configs


class WindowPicker(QDialog):
    """列出当前打开的窗口，勾选后连同位置尺寸一起记录到工作流。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("记录已打开的窗口")
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "先把窗口摆到你想要的位置和大小，再在这里勾选。\n"
            "启动工作流时会还原到你勾选那一刻的位置和尺寸。"
        ))
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)
        for w in winapi.list_windows():
            if not w["exe"]:
                continue
            label = f'{w["title"]}  —  {os.path.basename(w["exe"])}  ' \
                    f'[{w["w"]}×{w["h"]} @({w["x"]},{w["y"]})]'
            it = QListWidgetItem(label)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, w)
            self.list.addItem(it)
        lay.addWidget(self.list)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def selected(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                w = it.data(Qt.UserRole)
                out.append(settings_mod.new_workflow_item(
                    name=os.path.splitext(os.path.basename(w["exe"]))[0],
                    path=w["exe"], restore=True,
                    x=w["x"], y=w["y"], w=w["w"], h=w["h"],
                    maximized=w.get("maximized", False),
                ))
        return out


class ItemEditor(QDialog):
    """编辑单个工作流项：名称、参数、是否还原窗口、目标位置尺寸。"""

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑程序")
        self.item = dict(item)
        form = QFormLayout(self)

        self.name = QLineEdit(self.item.get("name", ""))
        self.path = QLineEdit(self.item.get("path", ""))
        self.args = QLineEdit(" ".join(self.item.get("args", [])))
        form.addRow("名称", self.name)
        row = QHBoxLayout()
        row.addWidget(self.path)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        w = QWidget(); w.setLayout(row)
        form.addRow("程序路径", w)
        form.addRow("启动参数", self.args)

        self.restore = QCheckBox("启动后还原到下面的位置和尺寸")
        self.restore.setChecked(bool(self.item.get("restore")))
        form.addRow(self.restore)

        self.x = QSpinBox(); self.x.setRange(-10000, 20000); self.x.setValue(self.item.get("x", 0))
        self.y = QSpinBox(); self.y.setRange(-10000, 20000); self.y.setValue(self.item.get("y", 0))
        self.w = QSpinBox(); self.w.setRange(0, 20000); self.w.setValue(self.item.get("w", 0))
        self.h = QSpinBox(); self.h.setRange(0, 20000); self.h.setValue(self.item.get("h", 0))
        geo = QHBoxLayout()
        for lab, sp in (("X", self.x), ("Y", self.y), ("宽", self.w), ("高", self.h)):
            geo.addWidget(QLabel(lab)); geo.addWidget(sp)
        gw = QWidget(); gw.setLayout(geo)
        form.addRow("窗口", gw)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _browse(self):
        fn, _ = QFileDialog.getOpenFileName(self, "选择程序", "", "程序 (*.exe);;所有文件 (*.*)")
        if fn:
            self.path.setText(fn)
            if not self.name.text():
                self.name.setText(os.path.splitext(os.path.basename(fn))[0])

    def result_item(self):
        args = [a for a in self.args.text().split(" ") if a]
        return settings_mod.new_workflow_item(
            name=self.name.text(), path=self.path.text(), args=args,
            restore=self.restore.isChecked(),
            x=self.x.value(), y=self.y.value(), w=self.w.value(), h=self.h.value(),
        )


class SettingsDialog(QDialog):
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.s = pet.settings
        self.setWindowTitle("井盖设置")
        self.resize(560, 480)

        # v0.3：工作流数据来自 config/ 下当前生效的 json（active_config 指向）
        self._active = self.s.get("active_config", configs.DEFAULT_NAME)
        if self._active not in configs.list_configs():
            self._active = configs.DEFAULT_NAME
        self._items = configs.load_config(self._active)

        tabs = QTabWidget()
        tabs.addTab(self._tab_workflow(), "启动工作流")
        tabs.addTab(self._tab_style(), "更改风格")
        tabs.addTab(self._tab_behavior(), "行为模式")
        tabs.addTab(self._tab_window(), "窗口")

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        lay.addWidget(close)

    # ---------- 工作流 ----------
    def _tab_workflow(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        # 顶部：配置文件管理（切换 / 新建 / 另存为 / 删除 / 导入 / 暂存）
        cfg_row = QHBoxLayout()
        cfg_row.addWidget(QLabel("当前配置"))
        self.cfg_combo = QComboBox()
        self.cfg_combo.currentIndexChanged.connect(self._cfg_on_combo)
        cfg_row.addWidget(self.cfg_combo, 1)
        lay.addLayout(cfg_row)

        cfg_btn_row = QHBoxLayout()
        for text, fn in (
            ("新建", self._cfg_new),
            ("另存为", self._cfg_saveas),
            ("删除", self._cfg_delete),
            ("导入配置", self._cfg_import),
            ("暂存当前桌面→临时", self._cfg_stash_latest),
        ):
            b = QPushButton(text); b.clicked.connect(fn); cfg_btn_row.addWidget(b)
        lay.addLayout(cfg_btn_row)

        lay.addWidget(QLabel(
            "按顺序启动下列程序。勾了“还原窗口”的会被移动到记录的位置和尺寸。\n"
            "下面的增删改会实时保存到上方选中的配置文件里。"
        ))
        self.wf_list = QListWidget()
        lay.addWidget(self.wf_list)

        row = QHBoxLayout()
        for text, fn in (
            ("添加程序", self._wf_add),
            ("记录已开窗口", self._wf_record),
            ("编辑", self._wf_edit),
            ("删除", self._wf_del),
            ("上移", lambda: self._wf_move(-1)),
            ("下移", lambda: self._wf_move(1)),
        ):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        lay.addLayout(row)

        run_row = QHBoxLayout()
        run_btn = QPushButton("▶ 立即启动工作流")
        run_btn.clicked.connect(self._wf_run)
        run_row.addWidget(run_btn)
        self.wf_status = QLabel("")
        run_row.addWidget(self.wf_status, 1)
        lay.addLayout(run_row)

        self._refresh_cfg_combo()
        self._refresh_wf()
        return w

    # ---------- 配置文件管理 ----------
    def _refresh_cfg_combo(self):
        """按 configs.list_configs 的顺序重建下拉框，选中当前 active。"""
        self.cfg_combo.blockSignals(True)
        self.cfg_combo.clear()
        names = configs.list_configs()
        for name in names:
            self.cfg_combo.addItem(configs.display_label(name), name)
        if self._active in names:
            self.cfg_combo.setCurrentIndex(names.index(self._active))
        self.cfg_combo.blockSignals(False)

    def _cfg_on_combo(self, idx):
        if idx < 0:
            return
        name = self.cfg_combo.itemData(idx)
        if name and name != self._active:
            self._cfg_switch(name)

    def _cfg_switch(self, name):
        """切换当前生效配置：更新指针、持久化、重载列表。"""
        self._active = name
        self.s["active_config"] = name
        self.pet.persist()
        self._items = configs.load_config(name)
        self._refresh_wf()

    def _cfg_new(self):
        text, ok = QInputDialog.getText(self, "新建配置", "配置文件名：")
        if not ok:
            return
        name = configs.unique_name(configs.normalize_name(text))
        if not configs.save_config(name, []):
            self._warn_write()
            return
        self._refresh_cfg_combo()
        self._select_and_switch(name)

    def _cfg_saveas(self):
        text, ok = QInputDialog.getText(
            self, "另存为", "把当前列表另存为：", text=self._active)
        if not ok:
            return
        name = configs.unique_name(configs.normalize_name(text))
        if not configs.save_config(name, self._items):
            self._warn_write()
            return
        self._refresh_cfg_combo()
        self._select_and_switch(name)

    def _cfg_delete(self):
        name = self._active
        if name in configs.PROTECTED:
            QMessageBox.information(
                self, "删除",
                f"{name} 是内置配置，删除只会清空它的列表，不会删掉文件。")
        target = configs.delete_config(name)
        self._refresh_cfg_combo()
        self._select_and_switch(target)

    def _cfg_import(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "导入工作流配置", "", "配置 (*.json);;所有文件 (*.*)")
        if not fn:
            return
        ok, result = configs.import_config(fn)
        if not ok:
            QMessageBox.warning(self, "导入配置", f"导入失败：{result}")
            return
        self._refresh_cfg_combo()
        self._select_and_switch(result)

    def _cfg_stash_latest(self):
        """抓当前桌面上所有打开着的窗口，写进 latest.json 并切过去。"""
        items = []
        for win in winapi.list_windows():
            if not win.get("exe"):
                continue
            items.append(settings_mod.new_workflow_item(
                name=os.path.splitext(os.path.basename(win["exe"]))[0],
                path=win["exe"], restore=True,
                x=win["x"], y=win["y"], w=win["w"], h=win["h"],
                maximized=win.get("maximized", False),
            ))
        if not items:
            QMessageBox.information(
                self, "暂存", "没抓到有程序的窗口，latest 未改动。")
            return
        if not configs.save_config(configs.LATEST_NAME, items):
            self._warn_write()
            return
        QMessageBox.information(
            self, "暂存",
            f"已把当前 {len(items)} 个窗口快照存进 {configs.LATEST_NAME}。")
        self._refresh_cfg_combo()
        self._select_and_switch(configs.LATEST_NAME)

    def _select_and_switch(self, name):
        """把下拉框选到 name（触发切换）；已是当前则手动切一次。"""
        for i in range(self.cfg_combo.count()):
            if self.cfg_combo.itemData(i) == name:
                if self.cfg_combo.currentIndex() == i:
                    self._cfg_switch(name)
                else:
                    self.cfg_combo.setCurrentIndex(i)
                return
        self._cfg_switch(name)

    def _warn_write(self):
        QMessageBox.warning(
            self, "无法保存",
            "写入 config 文件夹失败，可能是井盖被放在了没有写权限的目录"
            "（比如 C:\\Program Files）。\n请把井盖挪到普通目录再试。")

    # ---------- 列表（作用于当前配置） ----------
    def _refresh_wf(self):
        self.wf_list.clear()
        for it in self._items:
            mark = "  [还原窗口]" if it.get("restore") else ""
            self.wf_list.addItem(f'{it.get("name")}  ({it.get("path")}){mark}')

    def _wf_selected_row(self):
        r = self.wf_list.currentRow()
        return r if 0 <= r < len(self._items) else -1

    def _wf_add(self):
        fn, _ = QFileDialog.getOpenFileName(self, "选择程序", "", "程序 (*.exe);;所有文件 (*.*)")
        if fn:
            self._items.append(settings_mod.new_workflow_item(path=fn))
            self._commit_wf()

    def _wf_record(self):
        dlg = WindowPicker(self)
        if dlg.exec() == QDialog.Accepted:
            picked = dlg.selected()
            if picked:
                self._items.extend(picked)
                self._commit_wf()

    def _wf_edit(self):
        r = self._wf_selected_row()
        if r < 0:
            return
        dlg = ItemEditor(self._items[r], self)
        if dlg.exec() == QDialog.Accepted:
            self._items[r] = dlg.result_item()
            self._commit_wf()

    def _wf_del(self):
        r = self._wf_selected_row()
        if r < 0:
            return
        del self._items[r]
        self._commit_wf()

    def _wf_move(self, delta):
        r = self._wf_selected_row()
        if r < 0:
            return
        nr = r + delta
        if 0 <= nr < len(self._items):
            self._items[r], self._items[nr] = self._items[nr], self._items[r]
            self._commit_wf()
            self.wf_list.setCurrentRow(nr)

    def _commit_wf(self):
        """把当前列表写回当前配置文件。latest 内容变化可能影响下拉排序。"""
        if not configs.save_config(self._active, self._items):
            self._warn_write()
            return
        self._refresh_wf()
        if self._active == configs.LATEST_NAME:
            self._refresh_cfg_combo()

    def _wf_run(self):
        if not self._items:
            QMessageBox.information(self, "工作流", "当前配置里还没有添加任何程序。")
            return
        self.wf_status.setText("启动中…")
        wf_runner.run(
            self._items,
            progress=lambda msg: self.wf_status.setText(msg),
        )

    # ---------- 风格 ----------
    def _tab_style(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(
            "风格包 = 一个 .zip 或文件夹，里面放同名 gif：\n"
            "  idle.gif  walk.gif  drag.gif  sleep.gif  click.gif\n"
            "缺哪个状态就沿用默认井盖。"
        ))
        self.style_label = QLabel()
        self._refresh_style_label()
        lay.addWidget(self.style_label)

        row = QHBoxLayout()
        b1 = QPushButton("选择 .zip 风格包")
        b1.clicked.connect(self._style_zip)
        b2 = QPushButton("选择文件夹")
        b2.clicked.connect(self._style_folder)
        b3 = QPushButton("恢复默认井盖")
        b3.clicked.connect(self._style_reset)
        row.addWidget(b1); row.addWidget(b2); row.addWidget(b3)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _refresh_style_label(self):
        p = self.s.get("style_path") or ""
        self.style_label.setText("当前风格：" + (p if p else "默认井盖（内置）"))

    def _apply_style(self, path):
        self.s["style_path"] = path
        self.pet.persist()
        ok = self.pet.reload_style()
        self._refresh_style_label()
        if path and not ok:
            QMessageBox.warning(self, "风格", "没在这个风格包里找到任何可用的 gif，已保留原样。")

    def _style_zip(self):
        fn, _ = QFileDialog.getOpenFileName(self, "选择风格包", "", "风格包 (*.zip)")
        if fn:
            self._apply_style(fn)

    def _style_folder(self):
        d = QFileDialog.getExistingDirectory(self, "选择风格文件夹")
        if d:
            self._apply_style(d)

    def _style_reset(self):
        self._apply_style("")

    # ---------- 行为 ----------
    def _tab_behavior(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        box = QGroupBox("行为模式")
        bl = QVBoxLayout(box)
        self.rb_idle = QRadioButton("待机 — 一动不动待在原地")
        self.rb_wander = QRadioButton("散步 — 隔一会儿随机四处走动")
        grp = QButtonGroup(self)
        grp.addButton(self.rb_idle)
        grp.addButton(self.rb_wander)
        if self.s.get("behavior") == "idle":
            self.rb_idle.setChecked(True)
        else:
            self.rb_wander.setChecked(True)
        self.rb_idle.toggled.connect(
            lambda on: on and self._set_behavior("idle"))
        self.rb_wander.toggled.connect(
            lambda on: on and self._set_behavior("wander"))
        bl.addWidget(self.rb_idle)
        bl.addWidget(self.rb_wander)
        lay.addWidget(box)

        gbox = QGroupBox("重力")
        gl = QVBoxLayout(gbox)
        self.cb_gravity = QCheckBox("开启重力（松手会掉到地面）")
        self.cb_gravity.setChecked(bool(self.s.get("gravity")))
        self.cb_gravity.toggled.connect(self._set_gravity)
        gl.addWidget(self.cb_gravity)
        gl.addWidget(QLabel(
            "不勾 = 无重力：松手停在原地；靠近屏幕左右两侧时会趴到墙上，\n"
            "散步模式下还会沿着墙壁上下爬行。"
        ))
        lay.addWidget(gbox)
        lay.addStretch(1)
        return w

    def _set_behavior(self, mode):
        self.s["behavior"] = mode
        self.pet.persist()
        self.pet.set_behavior(mode)

    def _set_gravity(self, on):
        self.pet.persist_gravity(bool(on))

    # ---------- 窗口 ----------
    def _tab_window(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.cb_top = QCheckBox("保持井盖窗口始终在最前")
        self.cb_top.setChecked(bool(self.s.get("on_top")))
        self.cb_top.toggled.connect(self._set_on_top)
        lay.addWidget(self.cb_top)
        lay.addStretch(1)
        return w

    def _set_on_top(self, on):
        self.s["on_top"] = bool(on)
        self.pet.persist()
        self.pet.set_on_top(bool(on))
