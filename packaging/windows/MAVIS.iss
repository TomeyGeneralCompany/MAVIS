[Setup]
AppId={{D45AC6CD-BBC6-440D-986A-78101B58AEFD}
AppName=MAVIS
AppVersion=0.1.1
AppPublisher=Tomey General Company, LLC
DefaultDirName={localappdata}\Programs\MAVIS
DefaultGroupName=MAVIS
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist
OutputBaseFilename=MAVIS-Windows-Setup
SetupIconFile=..\..\build\windows\app\mavis.ico
UninstallDisplayIcon={app}\mavis.ico
Compression=lzma2/ultra64
LZMAUseSeparateProcess=yes
LZMADictionarySize=262144
LZMANumBlockThreads=1
SolidCompression=yes
[Files]
Source: "..\..\build\windows\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\MAVIS"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\windows_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\mavis.ico"
Name: "{group}\MAVIS Setup"; Filename: "{app}\python\python.exe"; Parameters: "-X utf8 ""{app}\windows_launcher.py"" --setup"; WorkingDir: "{app}"; IconFilename: "{app}\mavis.ico"
Name: "{autodesktop}\MAVIS"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\windows_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\mavis.ico"
[Run]
Filename: "{app}\python\python.exe"; Parameters: "-X utf8 ""{app}\windows_launcher.py"" --setup"; Description: "Set up local AI models (internet required)"; Flags: postinstall skipifsilent
[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""MAVIS Production"" /F"; Flags: runhidden; RunOnceId: "MAVISScheduler"
