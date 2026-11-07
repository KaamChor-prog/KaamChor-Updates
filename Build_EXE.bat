@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run Setup_and_Run.bat first, then close the app and run this file.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --icon app_icon.ico --name KaamChor_Pro --collect-all playwright Aryan_Remix.py
if errorlevel 1 (
 echo Build failed.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" Prepare_Release.py dist\KaamChor_Pro.exe
if errorlevel 1 (
 echo Release metadata failed. Do not publish this build.
 pause
 exit /b 1
)
copy /Y latest.json dist\latest.json >nul
echo EXE and latest.json ready in dist. Upload both to the matching GitHub release.
explorer "%~dp0dist"
pause
