@echo off
cd /d "%~dp0"
echo ========================================
echo  VALORANT OVERLAY SUITE - SMOOTH AIM
echo ========================================
echo.
echo Starting full suite with smooth aim...
echo.
echo CONTROLS:
echo   F1  = Toggle Smooth Aim Bot
echo   F2  = Toggle Recoil Recorder
echo   F3  = Toggle Sound Radar
echo   F4  = Toggle Clip Saver
echo   F9  = Toggle Visual Overlay (hide/show)
echo   F10 = Toggle ALL ON/OFF
echo   F7  = Quit
echo.
echo SMOOTH AIM:
echo   - Automatically moves mouse to nearest enemy
echo   - Smooth, not instant (adjustable)
echo   - Press K when on head
echo.
echo ========================================
python main.py
pause
