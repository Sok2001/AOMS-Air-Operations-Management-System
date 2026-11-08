#define MyAppName "AOMS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Sofia Karkar"
#define MyAppExeName "AOMS.exe"

[Setup]
AppId={{8E6B31A4-92F5-4D8A-A2C1-73D9F8B45120}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\AOMS
DefaultGroupName=AOMS

PrivilegesRequired=lowest
DisableProgramGroupPage=yes

OutputDir=..\dist
OutputBaseFilename=AOMS-Setup

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayName=AOMS - Air Operations Management System
UninstallDisplayIcon={app}\AOMS.exe

ArchitecturesInstallIn64BitMode=x64

CloseApplications=yes

[Tasks]
Name: "desktopicon"; \
    Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; \
    Flags: unchecked

[Files]
Source: "..\dist\AOMS.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AOMS"; \
    Filename: "{app}\AOMS.exe"

Name: "{autodesktop}\AOMS"; \
    Filename: "{app}\AOMS.exe"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\AOMS.exe"; \
    Description: "Launch AOMS"; \
    Flags: nowait postinstall skipifsilent
