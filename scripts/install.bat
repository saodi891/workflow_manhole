@echo off
REM 安装运行所需依赖。第一次使用先双击我。
REM 本脚本放在 scripts 目录下，会自动切换到项目根目录执行。
cd /d "%~dp0.."

echo 正在安装依赖 (PySide6)...
REM 走清华镜像，国内下载更稳更快；换成官方源就删掉 -i 那一段
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120
echo.
echo 安装完成。现在可以：
echo   - 双击 run.bat 直接运行看效果
echo   - 双击 build.bat 打包成 exe
pause
