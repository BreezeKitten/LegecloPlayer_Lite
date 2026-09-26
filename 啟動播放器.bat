@echo off
chcp 65001 >nul
title 《れじぇくろ！》輕量互動劇情播放器 (Lite 雲端隨選版)

echo ========================================================
echo    ✨ 《れじぇくろ！》輕量互動劇情播放器 (Lite 雲端隨選版) ✨
echo ========================================================
echo.
echo [*] 本版本為超輕量便攜版，點擊任意角色即可自動自官方雲端串流載入。
echo [*] 播放過的劇情與立繪將自動保存在本地，越玩越完整！
echo [*] 請保持此視窗開啟，關閉此視窗將停止播放器伺服器。
echo.

if exist "啟動播放器.exe" (
    echo [*] 正在以獨立免安裝執行檔啟動本機伺服器...
    echo.
    "啟動播放器.exe" 8888
    if %errorlevel% neq 0 (
        echo.
        echo [!] 執行檔啟動發生異常 (退出碼: %errorlevel%)
        echo [💡] 可能原因: 系統缺少 Microsoft Visual C++ 2015-2022 執行庫 (常見於純淨 Windows)
        echo      微軟官方安裝檔: https://aka.ms/vs/17/release/vc_redist.x64.exe (安裝後免重啟)
        echo.
        echo [*] 正在嘗試自動切換為本機 Python 環境啟動...
        echo.
        goto :run_python
    )
    echo.
    echo [*] 伺服器已正常退出。
    pause
    exit /b
)

:run_python

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 Python 環境！請確認電腦已安裝 Python 並加入 PATH 環境變數。
    echo.
    pause
    exit /b 1
)

echo [*] 正在檢查相依套件...
python -c "import UnityPy, imageio_ffmpeg, texture2ddecoder" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] 正在自動安裝必要相依套件...
    pip install UnityPy imageio-ffmpeg texture2ddecoder
)

echo [*] 正在啟動播放器本機伺服器...
echo.
python server.py 8888

pause
