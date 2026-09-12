@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt || goto :error

echo [2/3] Building single-file executable...
python -m PyInstaller --onefile --noconsole --icon fish.ico --name QuotePaste --clean quote_paste.py || goto :error

echo [3/3] Done! Output: dist\QuotePaste.exe
pause
exit /b 0

:error
echo Build failed. See output above.
pause
exit /b 1
