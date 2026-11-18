; MAVIS for Windows: graphical installer, WSL runtime and browser dashboard.
; Builds on Windows using Inno Setup 6. Does not install anything before consent.
#define AppVer "0.2.0"
[Setup]
AppId={{8C4F9309-35A6-4DFA-959A-ADFD8A71B27C}
AppName=MAVIS
AppVersion={#AppVer}
AppPublisher=Tomey General Company LLC
DefaultDirName={autopf}\MAVIS
DefaultGroupName=MAVIS
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=MAVIS-Setup-{#AppVer}-Windows
Compression=lzma2
SolidCompression=yes
SetupIconFile=MAVIS.ico
UninstallDisplayIcon={app}\MAVIS.ico
WizardStyle=modern

[Files]
Source: "MAVIS.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "install-wsl.sh"; DestDir: "{app}"; Flags: ignoreversion
Source: "mavis.deb"; DestDir: "{app}"; Flags: ignoreversion
Source: "MAVIS.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MAVIS"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\MAVIS.ps1"" -Action Launch"; IconFilename: "{app}\MAVIS.ico"; WorkingDir: "{app}"
Name: "{autodesktop}\MAVIS"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\MAVIS.ps1"" -Action Launch"; IconFilename: "{app}\MAVIS.ico"; WorkingDir: "{app}"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\MAVIS.ps1"" -Action Setup"; Description: "Configure MAVIS and Windows Subsystem for Linux"; Flags: postinstall runascurrentuser waituntilterminated
