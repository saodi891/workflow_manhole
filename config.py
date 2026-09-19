# -*- coding: utf-8 -*-
"""桌宠配置。改这里就能调整行为，不用动主逻辑。"""

# 窗口里显示的宠物尺寸（像素）。美术出图后按这个大小切帧最省事。
PET_SIZE = 128

# 帧动画播放速度：每帧停留毫秒数（越小越快）。
FRAME_INTERVAL_MS = 120

# 物理 / 行为参数
GRAVITY = 1.2            # 下落加速度
MAX_FALL_SPEED = 28      # 最大下落速度
WALK_SPEED = 2           # 闲逛时水平移动速度（像素/帧）
IDLE_MIN_MS = 2000       # 待机后最短多久才可能开始走动
IDLE_MAX_MS = 6000       # 待机后最长多久开始走动
WALK_MIN_MS = 1500       # 一次走动最短时长
WALK_MAX_MS = 4000       # 一次走动最长时长

ALWAYS_ON_TOP = True     # 是否总在最前
START_AT_BOTTOM = True   # 启动时是否落到屏幕底部
WALL_SNAP = 48           # 无重力时：松手离墙/地这么近(像素)就吸附上去

# 动画状态 -> 资源子文件夹名。把对应帧图（001.png、002.png…）放进去即可。
# 文件夹为空时会用内置的“井盖占位图”，方便你先跑起来看效果。
STATES = {
    "idle":  "assets/idle",
    "walk":  "assets/walk",
    "drag":  "assets/drag",
    "sleep": "assets/sleep",
    "click": "assets/click",
    "wait":  "assets/wait",
}

# 支持的图片后缀
IMAGE_EXTS = (".png", ".webp", ".gif")
