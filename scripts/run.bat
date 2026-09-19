@echo off
chcp 65001 >nul
REM 直接运行桌宠（不打包）。方便边调美术边看效果。
REM 本脚本放在 scripts\ 下，会自动切换到项目根目录执行。
cd /d "%~dp0.."
python pet.py
