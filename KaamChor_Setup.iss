; Optional installer: compile with Inno Setup 6 on Windows after Build_EXE.bat.
#define AppVersion "3.4.0"
[Setup]
AppId={{61416F9A-41C0-422F-B441-CE12BAEF3141}
AppName=KaamChor Pro
AppVersion={#AppVersion}
AppPublisher=KaamChor Pro
DefaultDirName={localappdata}\Programs\KaamChorPro
DefaultGroupName=KaamChor Pro
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=KaamChor_Setup
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\KaamChor_Pro.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Files]
Source: "dist\KaamChor_Pro.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\KaamChor Pro"; Filename: "{app}\KaamChor_Pro.exe"
Name: "{autodesktop}\KaamChor Pro"; Filename: "{app}\KaamChor_Pro.exe"
[Run]
Filename: "{app}\KaamChor_Pro.exe"; Description: "Open KaamChor Pro"; Flags: nowait postinstall skipifsilent
