@echo off
rem CUHK 校园地图本地启动：起 http.server 并打开浏览器
rem 关闭本窗口（或最小化的服务器窗口）即停止服务
cd /d "%~dp0"
start "" /min python -m http.server 12580
timeout /t 1 >nul
start "" http://localhost:12580/
