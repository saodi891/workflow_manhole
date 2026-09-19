# -*- coding: utf-8 -*-
"""井盖桌宠主程序。透明无边框窗口 + 拖拽 + 行为状态机 + 设置/工作流/风格。"""

import random
import sys

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QIcon, QTransform
from PySide6.QtWidgets import (
    QApplication, QLabel, QMenu, QSystemTrayIcon,
    QWidget, QPushButton, QVBoxLayout,
)

import config
import settings as settings_mod
import assets_loader
import wf_runner


class Pet(QLabel):
    def __init__(self):
        super().__init__()
        self.settings = settings_mod.load()
        self._settings_dialog = None

        # 无边框 + 工具窗口（不在任务栏显示）；置顶按设置决定
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._apply_window_flags(self.settings.get("on_top", True))
        self.resize(config.PET_SIZE, config.PET_SIZE)

        # 加载所有状态的帧（含风格包）
        self.states = assets_loader.load_states(
            config.PET_SIZE, self.settings.get("style_path", ""))
        self.state = "idle"
        self.frame_index = 0
        self.facing_left = True

        self._dragging = False
        self._moved = False        # 本次按下后是否真的拖动过（区分单击/拖拽）
        self._drag_offset = QPoint()
        self._press_pos = QPoint()
        self._panel_open = False
        self._panel_was_open = False

        self._behavior_ms_left = random.randint(config.IDLE_MIN_MS, config.IDLE_MAX_MS)
        self._walk_dir = 1      # 地面水平方向：1 右，-1 左
        self._climb_dir = -1    # 墙面竖直方向：-1 上，1 下
        self._vel_y = 0.0
        self.surface = "floor"  # floor / left / right（无重力时可趴墙）

        self._place_initial()
        self._apply_frame()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._next_frame)
        self._anim_timer.start(config.FRAME_INTERVAL_MS)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(16)

        self._build_tray()
        self._build_action_panels()

    # ---------- 设置接口（给 ui.py 调用） ----------
    def persist(self):
        settings_mod.save(self.settings)

    def set_behavior(self, mode):
        self.settings["behavior"] = mode
        if mode == "idle" and self.state == "walk":
            self._set_state("idle")

    def set_gravity(self, on):
        self.settings["gravity"] = bool(on)
        if on:
            # 开重力：从当前位置开始下落，并取消趴墙姿态
            self.surface = "floor"
            self._vel_y = 0.0
            self._apply_frame()

    def set_on_top(self, on):
        pos = self.pos()
        self._apply_window_flags(on)
        self.move(pos)
        self.show()  # 改 flags 后需要重新 show

    def reload_style(self):
        """按当前 style_path 重新加载外观。返回 True 表示加载正常。"""
        path = self.settings.get("style_path", "")
        loaded = assets_loader.load_style_pack(path, config.PET_SIZE) if path else {}
        self.states = assets_loader.load_states(config.PET_SIZE, path)
        self.frame_index = 0
        self._apply_frame()
        self.tray.setIcon(QIcon(self.states["idle"][0]))
        return (not path) or bool(loaded)

    def open_settings(self):
        from ui import SettingsDialog
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.finished.connect(self._on_settings_closed)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _on_settings_closed(self, _result):
        self._settings_dialog = None

    def _apply_window_flags(self, on_top):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    # ---------- 屏幕辅助 ----------
    def _screen_rect(self):
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _ground_y(self):
        return self._screen_rect().bottom() - self.height()

    def _place_initial(self):
        r = self._screen_rect()
        x = r.center().x() - self.width() // 2
        y = self._ground_y() if config.START_AT_BOTTOM else r.center().y()
        self.move(x, y)

    # ---------- 帧动画 ----------
    def _set_state(self, state):
        if state != self.state and state in self.states:
            self.state = state
            self.frame_index = 0
            self._apply_frame()

    def _next_frame(self):
        frames = self.states.get(self.state, [])
        if len(frames) > 1:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self._apply_frame()

    def _apply_frame(self):
        frames = self.states.get(self.state, [])
        if not frames:
            return
        pix = frames[self.frame_index % len(frames)]
        t = QTransform()
        if self.surface == "left":
            t.rotate(-90)   # 趴左墙：原本朝下的一面转向左（贴墙）
        elif self.surface == "right":
            t.rotate(90)    # 趴右墙
        elif self.state == "walk" and not self.facing_left:
            t.scale(-1, 1)  # 地面朝右走时水平翻转
        if not t.isIdentity():
            pix = pix.transformed(t, Qt.SmoothTransformation)
        self.setPixmap(pix)

    # ---------- 行为 / 物理 ----------
    def _tick(self):
        if self._dragging:
            return

        gravity = self.settings.get("gravity", False)
        if gravity:
            # 有重力：不在地面就下落
            ground = self._ground_y()
            if self.y() < ground:
                self._vel_y = min(self._vel_y + config.GRAVITY, config.MAX_FALL_SPEED)
                self.move(self.x(), min(self.y() + int(self._vel_y), ground))
                self.surface = "floor"
                if self.state not in ("wait",):
                    self._set_state("idle")
                return
            self._vel_y = 0.0
            self.surface = "floor"

        # 保持型状态：睡觉、等待（面板打开）时不自动移动
        if self.state in ("sleep", "wait"):
            return

        # 待机模式：不主动移动（无重力时停在原处/趴墙上）
        if self.settings.get("behavior") == "idle":
            self._set_state("idle")
            return

        # 散步模式：待机 / 移动 交替
        self._behavior_ms_left -= 16
        if self.state == "walk":
            self._move_along_surface(gravity)
        else:
            self._set_state("idle")

        if self._behavior_ms_left <= 0:
            if self.state == "walk":
                self._behavior_ms_left = random.randint(config.IDLE_MIN_MS, config.IDLE_MAX_MS)
                self._set_state("idle")
            else:
                self._behavior_ms_left = random.randint(config.WALK_MIN_MS, config.WALK_MAX_MS)
                self._start_walk()

    def _start_walk(self):
        if self.surface == "floor":
            self._walk_dir = random.choice((-1, 1))
            self.facing_left = self._walk_dir < 0
        else:
            self._climb_dir = random.choice((-1, 1))
        self._set_state("walk")

    def _move_along_surface(self, gravity):
        r = self._screen_rect()
        ground = self._ground_y()
        step = config.WALK_SPEED

        # 地面水平走。有重力→撞边缘掉头；无重力→爬上对应侧墙
        if gravity or self.surface == "floor":
            nx = self.x() + self._walk_dir * step
            if nx <= r.left():
                self.move(r.left(), self.y())
                if gravity:
                    self._walk_dir, self.facing_left = 1, False
                else:
                    self.surface, self._climb_dir = "left", -1
            elif nx >= r.right() - self.width():
                self.move(r.right() - self.width(), self.y())
                if gravity:
                    self._walk_dir, self.facing_left = -1, True
                else:
                    self.surface, self._climb_dir = "right", -1
            else:
                self.move(nx, self.y())
                self.facing_left = self._walk_dir < 0
            self._apply_frame()
            return

        # 无重力且在墙上：竖直爬，到顶折返，到底回到地面
        ny = self.y() + self._climb_dir * step
        if ny <= r.top():
            self.move(self.x(), r.top())
            self._climb_dir = 1
        elif ny >= ground:
            self.move(self.x(), ground)
            self._walk_dir = 1 if self.surface == "left" else -1
            self.facing_left = self._walk_dir < 0
            self.surface = "floor"
        else:
            self.move(self.x(), ny)
        self._apply_frame()

    # ---------- 鼠标交互 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._moved = False
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.pos()
            # 面板已展开时：一按下就立即收起（无论接下来是单击还是拖动）
            self._panel_was_open = self._panel_open
            if self._panel_open:
                self._hide_panel()
            e.accept()   # 先不切 drag，等真的移动了再切，以便区分单击

    def mouseMoveEvent(self, e):
        if not self._dragging:
            return
        gp = e.globalPosition().toPoint()
        if not self._moved and (gp - self._press_pos).manhattanLength() > 4:
            self._moved = True
            self._set_state("drag")
        if self._moved:
            self.move(gp - self._drag_offset)
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._dragging:
            return
        self._dragging = False
        e.accept()
        if not self._moved:
            # 未移动 = 单击：之前没展开才展开；之前展开的已在按下时收起
            if not self._panel_was_open:
                self._show_panel()
            return
        # 拖拽结束
        self._vel_y = 0.0
        self._behavior_ms_left = random.randint(config.IDLE_MIN_MS, config.IDLE_MAX_MS)
        if not self.settings.get("gravity", False):
            self._snap_to_surface()
        self._set_state("idle")
        self._apply_frame()

    def _snap_to_surface(self):
        r = self._screen_rect()
        if self.x() <= r.left() + config.WALL_SNAP:
            self.move(r.left(), self.y())
            self.surface = "left"
        elif self.x() >= r.right() - self.width() - config.WALL_SNAP:
            self.move(r.right() - self.width(), self.y())
            self.surface = "right"
        else:
            if self.y() >= self._ground_y() - config.WALL_SNAP:
                self.move(self.x(), self._ground_y())
            self.surface = "floor"   # 半空则悬停，动画按地面朝向

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._set_state("click")
            self._behavior_ms_left = 800
            e.accept()

    # ---------- 单击功能面板 ----------
    _PANEL_QSS = """
        QPushButton {
            background: rgba(28,28,34,225);
            color: #f2f2f2;
            border: 1px solid rgba(255,255,255,45);
            border-radius: 9px;
            padding: 7px 14px;
            font-size: 13px;
        }
        QPushButton:hover { background: rgba(64,64,78,238); }
        QPushButton:pressed { background: rgba(90,90,110,245); }
    """

    def _make_panel(self, buttons):
        w = QWidget(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        w.setAttribute(Qt.WA_TranslucentBackground)
        w.setStyleSheet(self._PANEL_QSS)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        made = []
        for text, fn in buttons:
            b = QPushButton(text, w)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            lay.addWidget(b)
            made.append(b)
        return w, made

    def _build_action_panels(self):
        self.left_panel, _ = self._make_panel([
            ("启动工作流", self._panel_workflow),
            ("设置", self._panel_settings),
            ("切换行为", self._panel_toggle_behavior),
        ])
        self.right_panel, rbtns = self._make_panel([
            ("睡觉", self._panel_toggle_sleep),
            ("更改重力", self._panel_toggle_gravity),
            ("退出井盖", QApplication.quit),
        ])
        self._sleep_btn = rbtns[0]

    def _position_panels(self):
        g = self.geometry()
        sr = self._screen_rect()
        gap = 12
        lp, rp = self.left_panel, self.right_panel
        lp.adjustSize(); rp.adjustSize()

        lx = g.x() - gap - lp.width()
        rx = g.x() + g.width() + gap
        if lx < sr.left():                      # 贴左墙：左面板放不下，挪到右侧
            lx = sr.left()
        if rx + rp.width() > sr.right():         # 贴右墙：右面板挪到能显示处
            rx = sr.right() - rp.width()
        ly = min(max(g.y() + (g.height() - lp.height()) // 2, sr.top()),
                 sr.bottom() - lp.height())
        ry = min(max(g.y() + (g.height() - rp.height()) // 2, sr.top()),
                 sr.bottom() - rp.height())
        lp.move(lx, ly)
        rp.move(rx, ry)

    def _show_panel(self):
        self._panel_open = True
        # 睡着时打开面板保持睡姿并显示“唤醒”，否则播放 wait
        self._sleep_btn.setText("唤醒" if self.state == "sleep" else "睡觉")
        if self.state != "sleep":
            self._set_state("wait")
        self._position_panels()
        for p in (self.left_panel, self.right_panel):
            p.show()
            p.raise_()

    def _hide_panel(self):
        self._panel_open = False
        self.left_panel.hide()
        self.right_panel.hide()
        if self.state == "wait":
            self._set_state("idle")

    def _panel_workflow(self):
        self._hide_panel()
        self._run_workflow()

    def _panel_settings(self):
        self._hide_panel()
        self.open_settings()

    def _panel_toggle_behavior(self):
        cur = self.settings.get("behavior", "idle")
        self._quick_behavior("wander" if cur == "idle" else "idle")
        self._hide_panel()

    def _panel_toggle_gravity(self):
        self._quick_toggle_gravity()
        self._hide_panel()

    def _panel_toggle_sleep(self):
        self._toggle_sleep()   # 睡觉<->唤醒；睡姿是保持型，不会被面板收起打断
        self._hide_panel()

    def contextMenuEvent(self, e):
        self._menu().exec(e.globalPos())

    # ---------- 托盘 / 菜单 ----------
    def _menu(self):
        m = QMenu()

        act_settings = QAction("设置…", m)
        act_settings.triggered.connect(self.open_settings)
        m.addAction(act_settings)

        act_workflow = QAction("启动工作流", m)
        act_workflow.setEnabled(bool(self.settings.get("workflow")))
        act_workflow.triggered.connect(self._run_workflow)
        m.addAction(act_workflow)

        m.addSeparator()

        # 行为模式快捷切换
        act_wander = QAction("散步模式", m)
        act_wander.setCheckable(True)
        act_wander.setChecked(self.settings.get("behavior") != "idle")
        act_wander.triggered.connect(lambda: self._quick_behavior("wander"))
        m.addAction(act_wander)

        act_idle = QAction("待机模式", m)
        act_idle.setCheckable(True)
        act_idle.setChecked(self.settings.get("behavior") == "idle")
        act_idle.triggered.connect(lambda: self._quick_behavior("idle"))
        m.addAction(act_idle)

        act_gravity = QAction("开启重力", m)
        act_gravity.setCheckable(True)
        act_gravity.setChecked(bool(self.settings.get("gravity")))
        act_gravity.triggered.connect(self._quick_toggle_gravity)
        m.addAction(act_gravity)

        act_top = QAction("保持最前", m)
        act_top.setCheckable(True)
        act_top.setChecked(bool(self.settings.get("on_top")))
        act_top.triggered.connect(self._quick_toggle_top)
        m.addAction(act_top)

        m.addSeparator()
        act_sleep = QAction("睡觉 / 唤醒", m)
        act_sleep.triggered.connect(self._toggle_sleep)
        m.addAction(act_sleep)

        act_center = QAction("回到屏幕中间", m)
        act_center.triggered.connect(self._place_initial)
        m.addAction(act_center)

        m.addSeparator()
        act_quit = QAction("退出", m)
        act_quit.triggered.connect(QApplication.quit)
        m.addAction(act_quit)
        return m

    def _quick_behavior(self, mode):
        self.settings["behavior"] = mode
        self.persist()
        self.set_behavior(mode)

    def _quick_toggle_top(self):
        on = not bool(self.settings.get("on_top"))
        self.settings["on_top"] = on
        self.persist()
        self.set_on_top(on)

    def _quick_toggle_gravity(self):
        on = not bool(self.settings.get("gravity"))
        self.persist_gravity(on)

    def persist_gravity(self, on):
        self.set_gravity(on)
        self.persist()

    def _run_workflow(self):
        items = self.settings.get("workflow") or []
        if items:
            wf_runner.run(items, progress=lambda msg: self.tray.showMessage(
                "工作流", msg, QSystemTrayIcon.Information, 1500))

    def _toggle_sleep(self):
        if self.state == "sleep":
            self._set_state("idle")
        else:
            self._set_state("sleep")
            self._behavior_ms_left = 10 ** 9

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(self.states["idle"][0]))
        self.tray.setToolTip("井盖桌宠")
        self.tray.setContextMenu(self._menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        # 单击/双击托盘图标都弹出菜单（每次重建以刷新勾选状态）
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            menu = self._menu()
            self.tray.setContextMenu(menu)
            menu.exec(QCursor.pos())


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = Pet()
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
