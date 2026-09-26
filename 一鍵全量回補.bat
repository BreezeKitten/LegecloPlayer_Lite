@echo off
chcp 65001 >nul
title 《れじぇくろ！》一鍵資源全量回補工具

if exist "一鍵全量回補.exe" (
    "一鍵全量回補.exe"
    exit /b
)

python 一鍵全量回補.py
if %errorlevel% neq 0 (
    pause
)
