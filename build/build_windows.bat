@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   Stock Multi-Agent Desktop - Windows .exe 一鍵打包工具
echo ============================================================

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
    echo [1/3] 偵測到虛擬環境 .venv
) else (
    set "PY_EXE=python"
    echo [1/3] 使用系統 Python
)

echo [2/3] 檢查並安裝必要套件 (包含 PyInstaller)...
"%PY_EXE%" -m pip install --upgrade pip >nul 2>&1
"%PY_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [錯誤] 套件安裝失敗，請確認已安裝 Python 3.10~3.12 並保持網路連線。
    pause
    exit /b 1
)

echo [3/3] 開始打包 StockMultiAgent.exe（約需 1~3 分鐘）...
"%PY_EXE%" build\build_desktop.py
if errorlevel 1 (
    echo.
    echo [錯誤] PyInstaller 打包失敗，請檢查上方錯誤訊息。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   打包完成！執行檔位於：dist\StockMultiAgent.exe
echo ============================================================
if exist "dist\StockMultiAgent.exe" (
    explorer /select,"%CD%\dist\StockMultiAgent.exe"
)
pause
