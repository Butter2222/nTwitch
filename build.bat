@echo off
REM Simple batch script to build TwitchViewer.exe

echo ============================================================
echo Building Twitch Terminal Viewer Executable
echo ============================================================
echo.

REM Install PyInstaller if needed
echo Checking for PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller!
        pause
        exit /b 1
    )
)

echo Building executable...
echo ------------------------------------------------------------
pyinstaller --name=TwitchViewer --onefile --console --icon=NONE --hidden-import=blessed.sequences --hidden-import=blessed.formatters --hidden-import=blessed.keyboard --hidden-import=blessed.terminal --hidden-import=asyncio --hidden-import=aiofiles --collect-all=blessed --clean twitch_viewer.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo BUILD FAILED!
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo BUILD SUCCESSFUL!
echo ============================================================
echo.
echo Executable location: dist\TwitchViewer.exe
echo.
echo You can now:
echo   1. Copy dist\TwitchViewer.exe to any location
echo   2. Run it to start the Twitch Terminal Viewer
echo   3. Config will be saved in: %%USERPROFILE%%\.twitch-terminal-config.json
echo.
echo Note: Streamlink must be installed on the target system:
echo   pip install streamlink
echo.
pause
