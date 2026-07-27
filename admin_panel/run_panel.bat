@echo off
REM ============================================================
REM   تشغيل لوحة تحكم البوت (Admin Panel)
REM   شغّل هذا الملف بالنقر المزدوج، ثم افتح المتصفح على:
REM   http://127.0.0.1:5000
REM ============================================================
cd /d "%~dp0.."
set PYTHONUTF8=1
"C:\ProgramData\anaconda3\python.exe" admin_panel\app.py
pause
