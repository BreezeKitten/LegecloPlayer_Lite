@echo off
chcp 65001 >nul
title 《れじぇくろ！》一鍵資源全量回補工具

if exist "一鍵全量回補.exe" (
    "一鍵全量回補.exe"
    if %errorlevel% neq 0 (
        echo.
        echo [!] 執行檔啟動遇到問題 (可能缺少 VC++ 運行庫: https://aka.ms/vs/17/release/vc_redist.x64.exe)
        echo [*] 正在嘗試以本機 Python 啟動...
        goto :run_python
    )
    exit /b
)

:run_python
python 一鍵全量回補.py
if %errorlevel% neq 0 (
    pause
)
