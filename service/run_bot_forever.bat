@echo off
chcp 65001 >nul
REM ============================================================
REM   تشغيل البوت بشكل دائم مع إعادة تشغيل تلقائية عند التوقف
REM   يكتب السجل في bot_service.log داخل مجلد المشروع
REM ============================================================
title بوت المسابقات الأكاديمية (تشغيل دائم)
cd /d "%~dp0.."
set PYTHONUTF8=1

:loop
echo [%date% %time%] --- بدء تشغيل البوت... >> bot_service.log
"C:\ProgramData\anaconda3\pythonw.exe" bot.py >> bot_service.log 2>&1
echo [%date% %time%] --- توقّف البوت، إعادة التشغيل بعد 5 ثوانٍ... >> bot_service.log
timeout /t 5 /nobreak >nul
goto loop
