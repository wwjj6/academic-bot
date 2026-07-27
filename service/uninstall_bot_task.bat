@echo off
chcp 65001 >nul
REM إيقاف البوت الدائم وحذف المهمة المجدولة
echo إيقاف البوت...
schtasks /End /TN "TelegramAcademicBot" 2>nul
echo حذف المهمة...
schtasks /Delete /TN "TelegramAcademicBot" /F
echo.
echo تم حذف التشغيل الدائم. لن يعمل البوت تلقائياً بعد الآن.
pause
