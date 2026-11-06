@echo off
cd /d "%~dp0"
where pyw >nul 2>&1 && start "" pyw -3 -m midphrase && exit /b 0
start "" py -3 -m midphrase
