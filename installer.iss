#define MyAppName "Learn with Hemant Exam System"
#define MyAppVersion "2.02"
#define MyAppExeName "LearnWithHemantOfflineExam.exe"

[Setup]
AppId={{7E881A55-3E08-4E79-82A2-5F816A002202}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Learn with Hemant
DefaultDirName={autopf}\Learn with Hemant Exam System
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer-output
OutputBaseFilename=LearnWithHemantExamSetup_V2.02
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "build-offline\LearnWithHemantOfflineExam.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "OFFLINE_V2.02_README.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch the examination system"; Flags: nowait postinstall skipifsilent
