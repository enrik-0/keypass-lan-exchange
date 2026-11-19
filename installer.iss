#define AppName "KeePass LAN Share"
#define AppVersion "0.2.0"
#define AppExe "KeePassLANShare.exe"
[Setup]
AppId={{D96B1D7A-99D1-487B-B911-62CBDF68C21F}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\KeePassLANShare
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=KeePassLANShare-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
CloseApplications=yes
[Tasks]
Name: "autostart"; Description: "Iniciar automáticamente con Windows"; Flags: checkedonce
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: unchecked
[Files]
Source: "dist\KeePassLANShare\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\KeePass LAN Share"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\KeePass LAN Share"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "KeePassLANShare"; ValueData: """{app}\{#AppExe}"" --background"; Flags: uninsdeletevalue; Tasks: autostart
[Run]
Filename: "{app}\{#AppExe}"; Description: "Iniciar KeePass LAN Share"; Flags: nowait postinstall skipifsilent
