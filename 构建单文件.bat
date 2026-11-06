@echo off
cd /d "%~dp0"
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name midphrase midphrase.py
echo.
echo 生成文件：dist\midphrase.exe
