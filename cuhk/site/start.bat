@echo off
rem CUHK 校园地图本地启动：起 http.server 并打开浏览器
cd /d "%~dp0"
start "" http://localhost:8765/
python -m http.server 8765
