@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -SetupOnly
if errorlevel 1 (pause & exit /b 1)
if exist ".tools\uv\uv.exe" (
    set "UV=.tools\uv\uv.exe"
) else (
    set "UV=uv"
)
"%UV%" pip install --python ".venv\Scripts\python.exe" pyinstaller
if errorlevel 1 (pause & exit /b 1)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name KeePassLANShare --collect-all zeroconf --collect-all keyring app.py
if errorlevel 1 (pause & exit /b 1)
echo Ejecutable: dist\KeePassLANShare\KeePassLANShare.exe
if /i not "%~1"=="/quiet" pause
