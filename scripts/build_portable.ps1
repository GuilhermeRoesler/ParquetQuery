#Requires -Version 5.1
<#
.SYNOPSIS
    Monta pacote portátil Windows (Python embeddable + dependências + app).

.PARAMETER Version
    Versão do release (ex.: 1.6.5).

.PARAMETER PythonVersion
    Versão do Python embeddable (ex.: 3.11.9).

.PARAMETER OutputDir
    Pasta de saída relativa à raiz do projeto (padrão: dist).

.PARAMETER RepoUrl
    URL do repositório GitHub para o LEIA-ME (ex.: https://github.com/user/repo).

.PARAMETER SkipInstaller
    Não gera o instalador Inno Setup (só o ZIP portátil).

.PARAMETER RequireInstaller
    Falha se o Inno Setup (ISCC) não estiver instalado. Usado no CI.

.PARAMETER LiteOnly
    Gera só o ZIP lite (código + bootstrap; exige Python do sistema na 1ª execução).

.PARAMETER SkipLite
    Não gera o ZIP lite junto com o pacote full (ignorado com -LiteOnly).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$PythonVersion = '3.11.9',
    [string]$OutputDir = 'dist',
    [string]$RepoUrl = '',
    [switch]$SkipInstaller,
    [switch]$RequireInstaller,
    [switch]$LiteOnly,
    [switch]$SkipLite
)

$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$DistRoot = Join-Path $Root $OutputDir
$BundleName = "ParquetQuery-$Version-win64"
$Staging = Join-Path $DistRoot $BundleName
$PythonDir = Join-Path $Staging 'python'
$LiteBundleName = "ParquetQuery-$Version-win64-lite"
$LiteStaging = Join-Path $DistRoot $LiteBundleName

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host ">> $Message"
}

function Copy-AppPayload {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Dest,
        [switch]$IncludeRequirements
    )

    $copyItems = @(
        'app.py',
        'LICENSE',
        'pq',
        'assets'
    )
    foreach ($item in $copyItems) {
        $source = Join-Path $Root $item
        if (-not (Test-Path $source)) {
            throw "Arquivo obrigatorio ausente: $item"
        }
        Copy-Item -Path $source -Destination (Join-Path $Dest $item) -Recurse -Force
    }

    $scriptsDir = Join-Path $Dest 'scripts'
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    $scriptFiles = @(
        'find_free_port.py',
        'windows_tray_launcher.py',
        'windows_lite_bootstrap.py'
    )
    foreach ($scriptName in $scriptFiles) {
        $src = Join-Path $Root "scripts\$scriptName"
        if (-not (Test-Path $src)) {
            throw "Arquivo obrigatorio ausente: scripts\$scriptName"
        }
        Copy-Item -Path $src -Destination (Join-Path $scriptsDir $scriptName) -Force
    }

    if ($IncludeRequirements) {
        foreach ($req in @('requirements.txt', 'requirements-portable-win.txt')) {
            $src = Join-Path $Root $req
            if (-not (Test-Path $src)) {
                throw "Arquivo obrigatorio ausente: $req"
            }
            Copy-Item -Path $src -Destination (Join-Path $Dest $req) -Force
        }
    }
}

function New-LitePackage {
    Write-Step "Preparando staging lite em $LiteStaging"
    if (Test-Path $LiteStaging) {
        Remove-Item $LiteStaging -Recurse -Force
    }
    New-Item -ItemType Directory -Path $LiteStaging -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $LiteStaging 'data') -Force | Out-Null
    New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

    Write-Step 'Copiando arquivos do pacote lite'
    Copy-AppPayload -Dest $LiteStaging -IncludeRequirements

    $liteBat = @'
@echo off
cd /d "%~dp0"
title Parquet Query (lite)
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 "%~dp0scripts\windows_lite_bootstrap.py"
  if errorlevel 1 pause
  exit /b %ERRORLEVEL%
)
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python "%~dp0scripts\windows_lite_bootstrap.py"
  if errorlevel 1 pause
  exit /b %ERRORLEVEL%
)
echo [ERRO] Python 3.10+ nao encontrado no PATH.
echo Instale em https://www.python.org/downloads/ e marque "Add to PATH".
echo Ou use o pacote completo win64-setup.exe / win64.zip (sem Python).
pause
exit /b 1
'@
    Set-Content -Path (Join-Path $LiteStaging 'Iniciar Parquet Query.bat') -Value $liteBat -Encoding Ascii

    $repoLine = if ($RepoUrl) { "Projeto: $RepoUrl" } else { 'Projeto: consulte o repositorio no GitHub.' }
    $leiaMeLite = @"
Parquet Query v$Version — Windows 64 bits (lite)
================================================

Este pacote NAO inclui Python. Na 1a execucao cria .venv e baixa as
dependencias (internet necessaria). Nas seguintes, sobe direto.

REQUISITOS
- Windows 10 ou 11 (64 bits)
- Python 3.10+ no PATH (instalador python.org com "Add to PATH")
- Internet na primeira execucao

INICIO RAPIDO
1. Instale com o setup-lite.exe OU extraia o ZIP lite
2. Use o atalho do menu Iniciar ou "Iniciar Parquet Query.bat"
3. Aguarde a configuracao (1a vez); o navegador abre e a bandeja fica ativa

PASTA DE INSTALACAO (setup)
%LOCALAPPDATA%\Programs\Parquet Query Lite

SEM PYTHON / OFFLINE
Use o pacote completo: ParquetQuery-$Version-win64-setup.exe ou
ParquetQuery-$Version-win64.zip (Python embutido).

$repoLine
"@
    Set-Content -Path (Join-Path $LiteStaging 'LEIA-ME.txt') -Value $leiaMeLite -Encoding UTF8

    Write-Step 'Criando ZIP lite'
    $liteZipPath = Join-Path $DistRoot "$LiteBundleName.zip"
    if (Test-Path $liteZipPath) {
        Remove-Item $liteZipPath -Force
    }
    Compress-Archive -Path $LiteStaging -DestinationPath $liteZipPath -CompressionLevel Optimal
    Write-Host "Pacote lite criado: $liteZipPath"

    $liteSetupPath = $null
    if (-not $SkipInstaller) {
        Write-Step 'Gerando instalador lite (Inno Setup)'
        $iscc = Find-ISCC
        if (-not $iscc) {
            $msg = 'Inno Setup 6 (ISCC.exe) nao encontrado. Instale de https://jrsoftware.org/isinfo.php ou use -SkipInstaller.'
            if ($RequireInstaller) {
                throw $msg
            }
            Write-Host "[AVISO] $msg" -ForegroundColor Yellow
        }
        else {
            $iss = Join-Path $Root 'installer\parquet-query-lite.iss'
            if (-not (Test-Path -LiteralPath $iss)) {
                throw "Script Inno Setup lite ausente: $iss"
            }
            $iconIco = Join-Path $Root 'assets\icon.ico'
            if (-not (Test-Path -LiteralPath $iconIco)) {
                throw 'Arquivo obrigatorio ausente: assets\icon.ico'
            }
            $liteSetupPath = Join-Path $DistRoot "ParquetQuery-$Version-win64-lite-setup.exe"
            if (Test-Path -LiteralPath $liteSetupPath) {
                Remove-Item -LiteralPath $liteSetupPath -Force
            }
            Invoke-Checked $iscc `
                "/DMyAppVersion=$Version" `
                "/DStagingDir=$LiteStaging" `
                "/DDistDir=$DistRoot" `
                "/DRepoRoot=$Root" `
                $iss
            if (-not (Test-Path -LiteralPath $liteSetupPath)) {
                throw "Instalador lite nao foi gerado em $liteSetupPath"
            }
            Write-Host "Instalador lite criado: $liteSetupPath"
        }
    }

    return @{
        Zip   = $liteZipPath
        Setup = $liteSetupPath
    }
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Comando falhou (codigo $LASTEXITCODE): $FilePath $($ArgumentList -join ' ')"
    }
}

function Find-ISCC {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
    )
    $fromPath = Get-Command iscc -ErrorAction SilentlyContinue
    if ($fromPath) {
        $candidates = @($fromPath.Source) + $candidates
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

if ($LiteOnly) {
    $lite = New-LitePackage
    Write-Host ''
    Write-Host "Pacote lite: $($lite.Zip)"
    if ($lite.Setup) {
        Write-Host "Instalador lite: $($lite.Setup)"
    }
    Write-Host "Pasta staging lite: $LiteStaging"
    exit 0
}

Write-Step "Preparando staging em $Staging"
if (Test-Path $Staging) {
    Remove-Item $Staging -Recurse -Force
}
New-Item -ItemType Directory -Path $Staging -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Staging 'data') -Force | Out-Null
New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null

Write-Step "Baixando Python embeddable $PythonVersion"
$embedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$embedZip = Join-Path $env:TEMP "python-embed-$PythonVersion.zip"
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -UseBasicParsing
Expand-Archive -Path $embedZip -DestinationPath $PythonDir -Force

$pyMajorMinor = -join (($PythonVersion -split '\.')[0..1])
$pthFile = Get-ChildItem $PythonDir -Filter "python*._pth" | Select-Object -First 1
if (-not $pthFile) {
    throw "Arquivo python*._pth nao encontrado em $PythonDir"
}
$pthLines = @(
    "python$pyMajorMinor.zip",
    '.',
    'Lib\site-packages',
    'import site'
)
Set-Content -Path $pthFile.FullName -Value $pthLines -Encoding Ascii

$sitePackages = Join-Path $PythonDir 'Lib\site-packages'
New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null

Write-Step 'Instalando pip'
$getPip = Join-Path $env:TEMP 'get-pip.py'
Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getPip -UseBasicParsing
$pyExe = Join-Path $PythonDir 'python.exe'
Invoke-Checked $pyExe $getPip '--no-warn-script-location'

Write-Step 'Instalando dependencias do app (incl. bandeja Windows)'
$requirements = Join-Path $Root 'requirements-portable-win.txt'
if (-not (Test-Path $requirements)) {
    throw 'Arquivo obrigatorio ausente: requirements-portable-win.txt'
}
Invoke-Checked $pyExe '-m' 'pip' 'install' '-r' $requirements '--no-warn-script-location'

Write-Step 'Copiando arquivos do app'
Copy-AppPayload -Dest $Staging

Write-Step 'Gerando launchers e LEIA-ME'
# Atalho sem console: pythonw + bandeja. O .bat só dispara e fecha.
$launcherBat = @'
@echo off
cd /d "%~dp0"
if not exist "%~dp0python\pythonw.exe" (
  echo [ERRO] Python embutido nao encontrado. Reinstale o pacote.
  pause
  exit /b 1
)
start "" "%~dp0python\pythonw.exe" "%~dp0scripts\windows_tray_launcher.py"
exit /b 0
'@
Set-Content -Path (Join-Path $Staging 'Iniciar Parquet Query.bat') -Value $launcherBat -Encoding Ascii

$repoLine = if ($RepoUrl) { "Projeto: $RepoUrl" } else { 'Projeto: consulte o repositorio no GitHub.' }
$leiaMe = @"
Parquet Query v$Version — Windows 64 bits
=========================================

INICIO RAPIDO
1. Coloque seus arquivos .parquet ou .csv na pasta data\
2. De um duplo clique em "Iniciar Parquet Query.bat" (ou use o atalho do instalador)
3. O navegador abre sozinho; um icone fica na bandeja do sistema

REQUISITOS
- Windows 10 ou 11 (64 bits)
- Nao e necessario instalar Python

USO DA BANDEJA
- Clique no icone (ou "Abrir no navegador") para reabrir o app
- "Abrir pasta data" — pasta dos arquivos
- "Sair" — encerra o servidor e remove o icone
- Se o app ja estiver rodando, um novo clique so reabre o navegador

AVISO
- O Windows pode exibir alerta de seguranca (app nao assinado). Escolha
  "Mais informacoes" > "Executar assim mesmo" se confiar na origem.

$repoLine
"@
Set-Content -Path (Join-Path $Staging 'LEIA-ME.txt') -Value $leiaMe -Encoding UTF8

Write-Step 'Criando arquivo ZIP'
$zipPath = Join-Path $DistRoot "$BundleName.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path $Staging -DestinationPath $zipPath -CompressionLevel Optimal

$setupPath = $null
if (-not $SkipInstaller) {
    Write-Step 'Gerando instalador Inno Setup'
    $iscc = Find-ISCC
    if (-not $iscc) {
        $msg = 'Inno Setup 6 (ISCC.exe) nao encontrado. Instale de https://jrsoftware.org/isinfo.php ou use -SkipInstaller.'
        if ($RequireInstaller) {
            throw $msg
        }
        Write-Host "[AVISO] $msg" -ForegroundColor Yellow
    }
    else {
        $iss = Join-Path $Root 'installer\parquet-query.iss'
        if (-not (Test-Path -LiteralPath $iss)) {
            throw "Script Inno Setup ausente: $iss"
        }
        $iconIco = Join-Path $Root 'assets\icon.ico'
        if (-not (Test-Path -LiteralPath $iconIco)) {
            throw 'Arquivo obrigatorio ausente: assets\icon.ico'
        }
        $setupPath = Join-Path $DistRoot "ParquetQuery-$Version-win64-setup.exe"
        if (Test-Path -LiteralPath $setupPath) {
            Remove-Item -LiteralPath $setupPath -Force
        }
        Invoke-Checked $iscc `
            "/DMyAppVersion=$Version" `
            "/DStagingDir=$Staging" `
            "/DDistDir=$DistRoot" `
            "/DRepoRoot=$Root" `
            $iss
        if (-not (Test-Path -LiteralPath $setupPath)) {
            throw "Instalador nao foi gerado em $setupPath"
        }
    }
}

Write-Host ''
Write-Host "Pacote criado: $zipPath"
if ($setupPath) {
    Write-Host "Instalador criado: $setupPath"
}
Write-Host "Pasta staging: $Staging"

if (-not $SkipLite) {
    $lite = New-LitePackage
    Write-Host "Pacote lite: $($lite.Zip)"
    if ($lite.Setup) {
        Write-Host "Instalador lite: $($lite.Setup)"
    }
    Write-Host "Pasta staging lite: $LiteStaging"
}
