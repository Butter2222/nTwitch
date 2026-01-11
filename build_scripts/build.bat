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

REM Change to project root
cd ..

echo Building executable...
echo ------------------------------------------------------------
pyinstaller --name=nTwitch --onefile --console --icon=NONE --distpath=build_scripts/dist --workpath=build_scripts/build --specpath=build_scripts --hidden-import=blessed.sequences --hidden-import=blessed.formatters --hidden-import=blessed.keyboard --hidden-import=blessed.terminal --hidden-import=asyncio --hidden-import=aiofiles --hidden-import=src.config_manager --hidden-import=src.setup --hidden-import=src.stream_manager --hidden-import=src.chat_client --hidden-import=src.terminal_ui --hidden-import=src.recording_manager --hidden-import=src.clip_manager --hidden-import=src.input_handler --collect-all=blessed --paths=src --clean nTwitch.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo BUILD FAILED!
    echo ============================================================
    cd build_scripts
    pause
    exit /b 1
)

echo.
echo ============================================================
echo BUILD SUCCESSFUL!
echo ============================================================
echo.
echo Executable location: build_scripts\dist\nTwitch.exe
echo.
echo You can now:
echo   1. Copy build_scripts\dist\nTwitch.exe to any location
echo   2. Run it to start the Twitch Terminal Viewer
echo   3. Config will be saved in: %%USERPROFILE%%\.twitch-terminal-config.json
echo.
echo Note: Streamlink must be installed on the target system:
echo   pip install streamlink
echo.
cd build_scripts
pause
