@echo off
chcp 65001 >nul
REM تشغيل سكربت تسجيل المهمة المجدولة (بنقرة مزدوجة)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_bot_task.ps1"
echo.
echo لتشغيل البوت الان فورا:
schtasks /Run /TN "TelegramAcademicBot"
echo.
pause
