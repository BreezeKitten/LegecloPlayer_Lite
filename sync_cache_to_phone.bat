@echo off
chcp 65001 >nul
title LegecloPlayer - 同步離線資源至手機
cd /d "%~dp0"
python sync_cache_to_phone.py
pause
