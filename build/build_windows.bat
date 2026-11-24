@echo off
setlocal

echo ============================================================
echo   Stock Multi-Agent Desktop - Windows EXE Builder
echo ============================================================

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
    echo [1/3] Using virtual environment: .venv
) else (
    set "PY_EXE=python"
    echo [1/3] Using system Python
)

echo [2/3] Installing and verifying dependencies...
"%PY_EXE%" -m pip install --upgrade pip >nul 2>&1
"%PY_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed. Check Python 3.10-3.12 and internet connection.
    pause
    exit /b 1
)

echo [3/3] Building StockMultiAgent.exe with PyInstaller...
"%PY_EXE%" build\build_desktop.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Please inspect the messages above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build Succeeded! Output: dist\StockMultiAgent.exe
echo ============================================================
if exist "dist\StockMultiAgent.exe" (
    explorer /select,"%CD%\dist\StockMultiAgent.exe"
)
pause
