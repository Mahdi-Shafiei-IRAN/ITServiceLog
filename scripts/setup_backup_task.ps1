<#
    ثبت بکاپ روزانه‌ی خودکار در Task Scheduler ویندوز (روی همین سیستم).

    هر روز ساعت ۱۳:۰۰ برنامه‌ی نصب‌شده با --backup اجرا می‌شود، از دیتابیس سرور
    (آدرس داخل config.json کنار برنامه) یک فایل بکاپ می‌سازد و فقط ۳ روز آخر را نگه می‌دارد.
    اگر سیستم ساعت ۱۳ خاموش بود، به‌محض روشن شدن/ورود اجرا می‌شود.

    اجرا:
        powershell -ExecutionPolicy Bypass -File scripts\setup_backup_task.ps1
        powershell -ExecutionPolicy Bypass -File scripts\setup_backup_task.ps1 -BackupDir "\\it-shafiei\Backups" -Time 13:00
#>
param(
    [string]$BackupDir = "D:\Backups\ITServiceLog",
    [string]$Time = "13:00",
    [int]$Keep = 3,
    [string]$Exe = "$env:ProgramFiles\ITServiceLog\ITServiceLog.exe"
)

$ErrorActionPreference = "Stop"
$TaskName = "ITServiceLog Daily Backup"

if (-not (Test-Path $Exe)) { throw "Program not found: $Exe" }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$action = New-ScheduledTaskAction -Execute $Exe -Argument "--backup `"$BackupDir`" --keep $Keep" `
    -WorkingDirectory (Split-Path $Exe)
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description "Daily backup of the ITServiceLog server database (keeps last $Keep days)." `
    -Force | Out-Null

Write-Host "Scheduled '$TaskName' daily at $Time -> $BackupDir (keep $Keep)" -ForegroundColor Green
