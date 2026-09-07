; اسکریپت Inno Setup برای ساخت نصب‌کننده‌ی آفلاین ITServiceLog
; نسخه از طریق /DMyAppVersion از build.ps1 پاس داده می‌شود (پیش‌فرض 1.0.0)

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "IT Service Log"
#define MyAppExeName "ITServiceLog.exe"
#define MyAppPublisher "IT Department"

[Setup]
AppId={{8B2E5F1A-9C4D-4E7B-A3F6-1D2C3B4A5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\ITServiceLog
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; نصب برای همه‌ی کاربران (نیازمند دسترسی مدیر). برای نصب تک‌کاربره
; مقدار را به lowest تغییر دهید و DefaultDirName را {localappdata} کنید.
PrivilegesRequired=admin
OutputDir=release
OutputBaseFilename=ITServiceLog-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
; هر نسخه‌ی جدید روی نسخه‌ی قبلی به‌درستی به‌روزرسانی می‌شود (همان AppId)
UninstallDisplayName={#MyAppName} {#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "ایجاد میانبر روی دسکتاپ"; GroupDescription: "میانبرها:"; Flags: unchecked

[Files]
; کل خروجی PyInstaller (پوشه‌ی onedir) را کپی می‌کند
Source: "dist\ITServiceLog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; آیکون برنامه کنار فایل اجرایی تا شورتکات‌ها همیشه لوگو را نشان دهند
Source: "assets\app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"
Name: "{group}\حذف {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "اجرای {#MyAppName}"; Flags: nowait postinstall skipifsilent
