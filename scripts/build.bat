@echo off
chcp 65001 >nul
REM ============================================================
REM  一键打包井盖桌宠为 exe（Windows）
REM  第一次用先双击 install.bat 装依赖，再双击本文件。
REM  本脚本放在 scripts\ 下，会自动切换到项目根目录执行。
REM ============================================================
cd /d "%~dp0.."

echo [1/2] 检查 PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo   未安装，正在安装 pyinstaller...
    python -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120
)

echo [2/2] 开始打包...
REM --windowed   不弹黑色命令行窗口
REM --onefile    打包成单个 exe
REM --add-data   把 assets 一起塞进 exe（Windows 用分号分隔）
REM --icon       exe 图标，根目录有 icon.ico 就用（可选）
REM --distpath . 把 exe 直接输出到项目根目录
REM --workpath / --specpath  把打包中间产物收进 build\，保持根目录干净
set ICON_ARG=
if exist icon.ico set ICON_ARG=--icon icon.ico

REM add-data 源用绝对路径：因为 --specpath 改了 spec 所在目录，
REM 相对路径会以 spec 目录为基准找不到 assets。
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name 井盖桌宠 ^
  --add-data "%CD%\assets;assets" ^
  %ICON_ARG% ^
  --distpath . ^
  --workpath build ^
  --specpath build ^
  pet.py

echo.
echo 打包完成。exe 就在项目根目录：井盖桌宠.exe
pause
