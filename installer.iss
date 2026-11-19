#define AppName "KeePass LAN Share"
#define AppVersion "0.2.2"
#define AppExe "KeePassLANShare.exe"
#define FwTcpRule "KeePass LAN Share TCP 43187"
#define FwMdnsRule "KeePass LAN Share mDNS 5353"
[Setup]
AppId={{D96B1D7A-99D1-487B-B911-62CBDF68C21F}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\KeePassLANShare
DefaultGroupName={#AppName}
PrivilegesRequired=admin
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
; Inbound rules for the transfer port and mDNS discovery, limited to the Private profile.
; Delete first so reinstalls/upgrades never leave duplicate rules.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FwTcpRule}"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FwTcpRule}"" dir=in action=allow protocol=TCP localport=43187 profile=private"; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FwMdnsRule}"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FwMdnsRule}"" dir=in action=allow protocol=UDP localport=5353 profile=private"; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "Iniciar KeePass LAN Share"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FwTcpRule}"""; Flags: runhidden waituntilterminated; RunOnceId: "FwTcp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FwMdnsRule}"""; Flags: runhidden waituntilterminated; RunOnceId: "FwMdns"
