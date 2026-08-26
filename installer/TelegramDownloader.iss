; Inno Setup Script for Telegram Downloader (Windows 11 Production 24/7 Server)

#define MyAppName "Telegram Downloader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Telegram Downloader Project"
#define MyAppURL "https://github.com/dipinkumarak-netizen/TelegramMediaDownloader.git"
#define MyAppExeName "TelegramDownloader.exe"

[Setup]
AppId={{D8E5F1A4-7B32-48F1-9321-72B68E426F9A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\Output
OutputBaseFilename=TelegramDownloader-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startservice"; Description: "Automatically start Telegram Downloader 24/7 background service"; GroupDescription: "Service Options:"

[Files]
Source: "..\dist\TelegramDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{commonappdata}\TelegramDownloader"; Permissions: authusers-full
Name: "{commonappdata}\TelegramDownloader\config"; Permissions: authusers-full
Name: "{commonappdata}\TelegramDownloader\database"; Permissions: authusers-full
Name: "{commonappdata}\TelegramDownloader\logs"; Permissions: authusers-full
Name: "{commonappdata}\TelegramDownloader\session"; Permissions: authusers-full
Name: "{commonappdata}\TelegramDownloader\temp"; Permissions: authusers-full

[Icons]
Name: "{group}\{#MyAppName} Dashboard"; Filename: "http://localhost:8787"
Name: "{group}\{#MyAppName} Tray Companion"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--tray"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} Dashboard"; Filename: "http://localhost:8787"; Tasks: desktopicon

[Run]
; Install Windows Service
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install-service"; Flags: runhidden waituntilterminated; StatusMsg: "Registering Windows Background Service..."
; Start Windows Service if selected
Filename: "{app}\{#MyAppExeName}"; Parameters: "--start-service"; Flags: runhidden waituntilterminated; Tasks: startservice; StatusMsg: "Starting Telegram Downloader Service..."
; Open Web Dashboard in default browser
Filename: "http://localhost:8787"; Description: "Open Telegram Downloader Dashboard"; Flags: postinstall shellexec nowait

[UninstallRun]
; Stop and remove Windows Service prior to removing files
Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop-service"; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Parameters: "--remove-service"; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\TelegramDownloader"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Ensure all data, database, sessions, and configuration are purged for clean reinstallation
    DelTree(ExpandConstant('{commonappdata}\TelegramDownloader'), True, True, True);
  end;
end;
