@echo off
setlocal
cd /d "%~dp0"
call build-exe.bat /quiet
if errorlevel 1 exit /b 1
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 no encontrado. Instala Inno Setup en Windows para generar el instalador.
  echo El ejecutable sin instalador esta en dist\KeePassLANShare\KeePassLANShare.exe
  pause
  exit /b 1
)
"%ISCC%" installer.iss
if errorlevel 1 exit /b 1
echo Instalador: installer-output\KeePassLANShare-Setup.exe
pause
