@echo off
cd /d "%~dp0"
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name midphrase --paths . midphrase/__main__.py
echo.
echo 生成文件：dist\midphrase.exe
