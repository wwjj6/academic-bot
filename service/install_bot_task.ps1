# ============================================================
#  تسجيل البوت كمهمة مجدولة تعمل تلقائياً عند تسجيل الدخول
#  مع إعادة تشغيل تلقائية عند التوقف. لا يحتاج أي تحميل.
# ============================================================
$ErrorActionPreference = "Stop"

# مجلد المشروع = المجلد الأصل لمجلد service
$ProjectDir = Split-Path -Parent $PSScriptRoot
$BotScript  = Join-Path $ProjectDir "bot.py"

# اختيار مفسّر بايثون (pythonw = بلا نافذة)
$Python = "C:\ProgramData\anaconda3\pythonw.exe"
if (-not (Test-Path $Python)) { $Python = "C:\ProgramData\anaconda3\python.exe" }
if (-not (Test-Path $Python)) {
    Write-Host "[خطأ] لم يُعثر على بايثون في C:\ProgramData\anaconda3" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $BotScript)) {
    Write-Host "[خطأ] لم يُعثر على bot.py في $ProjectDir" -ForegroundColor Red
    exit 1
}

$TaskName = "TelegramAcademicBot"

$Action = New-ScheduledTaskAction -Execute $Python `
    -Argument "`"$BotScript`"" -WorkingDirectory $ProjectDir

# يعمل عند تسجيل دخول المستخدم الحالي
$Trigger = New-ScheduledTaskTrigger -AtLogOn

# إعدادات: إعادة تشغيل عند الفشل كل دقيقة، بلا حد زمني، يبدأ متى أمكن
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Description "بوت المسابقات الأكاديمية - كلية الطب | جامعة حجة" `
    -Force | Out-Null

Write-Host ""
Write-Host "تم تسجيل المهمة: $TaskName" -ForegroundColor Green
Write-Host "  المفسّر: $Python"
Write-Host "  البوت:   $BotScript"
Write-Host ""
Write-Host "سيعمل البوت تلقائياً عند كل تسجيل دخول، ويُعاد تشغيله إذا توقّف."
Write-Host "لتشغيله الآن فوراً دون إعادة تسجيل الدخول، شغّل:" -ForegroundColor Yellow
Write-Host "  schtasks /Run /TN `"$TaskName`""
