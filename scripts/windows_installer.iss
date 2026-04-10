[Setup]
AppName=Matika
AppVersion=1.0.6
WizardStyle=modern
DefaultDirName={autopf}\Matika
DefaultGroupName=Matika
UninstallDisplayIcon={app}\matika.exe
Compression=lzma2
SolidCompression=yes
OutputDir=..
OutputBaseFilename=matika-windows-setup

[Files]
Source: "..\dist\matika.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\INSTALL_GUIDE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\COPYRIGHT.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Matika"; Filename: "{app}\matika.exe"
Name: "{autodesktop}\Matika"; Filename: "{app}\matika.exe"
Name: "{autodesktop}\Matika Dashboard"; Filename: "http://127.0.0.1:8000"; IconFilename: "{app}\matika.exe"

[Run]
Filename: "{app}\matika.exe"; Description: "Launch Matika"; Flags: nowait postinstall skipifsilent
