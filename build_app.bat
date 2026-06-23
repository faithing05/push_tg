@echo off
setlocal

pyinstaller -y --noconsole --exclude-module PySide6 --name TgVkNotifier desktop_app.py

endlocal
