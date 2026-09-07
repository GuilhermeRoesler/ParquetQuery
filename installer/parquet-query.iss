; Instalador Windows do Parquet Query (Inno Setup 6).
; Compilado por scripts/build_portable.ps1 via ISCC com /D...
;
; Defines esperados (passados na linha de comando):
;   MyAppVersion  — ex.: 1.6.5
;   StagingDir    — pasta do pacote portátil já montado
;   DistDir       — pasta de saída do .exe
;   RepoRoot      — raiz do repositório (para ícone/licença)

#ifndef MyAppVersion
  #error MyAppVersion deve ser passado com /DMyAppVersion=X.Y.Z
#endif
#ifndef StagingDir
  #error StagingDir deve ser passado com /DStagingDir=...
#endif
#ifndef DistDir
  #error DistDir deve ser passado com /DDistDir=...
#endif
#ifndef RepoRoot
  #error RepoRoot deve ser passado com /DRepoRoot=...
#endif

#define MyAppName "Parquet Query"
#define MyAppPublisher "Guilherme Roesler"
#define MyAppExeName "Iniciar Parquet Query.bat"
#define MyAppId "{{A7C3E91F-4B2D-4E8A-9F15-6D2C8B1A0E47}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Parquet Query
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#RepoRoot}\LICENSE
OutputDir={#DistDir}
OutputBaseFilename=ParquetQuery-{#MyAppVersion}-win64-setup
SetupIconFile={#RepoRoot}\assets\icon.ico
UninstallDisplayIcon={app}\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0
InfoAfterFile={#StagingDir}\LEIA-ME.txt
CloseApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#StagingDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
