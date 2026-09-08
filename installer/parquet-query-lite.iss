; Instalador Windows lite do Parquet Query (Inno Setup 6).
; Sem Python embutido — atalho chama Iniciar Parquet Query.bat (bootstrap + .venv).
; Compilado por scripts/build_portable.ps1 via ISCC com /D...
;
; Defines esperados:
;   MyAppVersion  — ex.: 1.6.5
;   StagingDir    — pasta do pacote lite já montado
;   DistDir       — pasta de saída do .exe
;   RepoRoot      — raiz do repositório (ícone/licença)

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

#define MyAppName "Parquet Query (lite)"
#define MyAppPublisher "Guilherme Roesler"
#define MyAppExeName "Iniciar Parquet Query.bat"
; AppId distinto do instalador full para coexistir no mesmo PC.
#define MyAppId "{{B8D4F02A-5C3E-4F9B-A026-7E3D9C2B1F58}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Parquet Query Lite
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#RepoRoot}\LICENSE
OutputDir={#DistDir}
OutputBaseFilename=ParquetQuery-{#MyAppVersion}-win64-lite-setup
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
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

; .venv e .runtime são criados na 1ª execução — limpar na desinstalação.
[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\.runtime"
