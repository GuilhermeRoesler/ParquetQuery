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
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$PythonVersion = '3.11.9',
    [string]$OutputDir = 'dist',
    [string]$RepoUrl = ''
)

$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$DistRoot = Join-Path $Root $OutputDir
$BundleName = "ParquetQuery-$Version-win64"
$Staging = Join-Path $DistRoot $BundleName
$PythonDir = Join-Path $Staging 'python'

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host ">> $Message"
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

Write-Step 'Instalando dependencias do app'
$requirements = Join-Path $Root 'requirements.txt'
Invoke-Checked $pyExe '-m' 'pip' 'install' '-r' $requirements '--no-warn-script-location'

Write-Step 'Copiando arquivos do app'
$copyItems = @(
    'app.py',
    'find_free_port.py',
    'data_store.py',
    'pq_dax_translator.py',
    'pq_m_translator.py',
    'pq'
)
foreach ($item in $copyItems) {
    $source = Join-Path $Root $item
    if (-not (Test-Path $source)) {
        throw "Arquivo obrigatorio ausente: $item"
    }
    Copy-Item -Path $source -Destination (Join-Path $Staging $item) -Recurse -Force
}

Write-Step 'Gerando launchers e LEIA-ME'
$launcherPs1 = @'
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$Root = $PSScriptRoot
$Host.UI.RawUI.WindowTitle = 'Parquet Query'
$Python = Join-Path $Root 'python\python.exe'

if (-not (Test-Path $Python)) {
    Write-Host '[ERRO] Python embutido nao encontrado. Reinstale o pacote.' -ForegroundColor Red
    pause
    exit 1
}

$dataDir = Join-Path $Root 'data'
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}

Write-Host ''
Write-Host ' Parquet Query'
Write-Host ' ============='
Write-Host ''

$port = (& $Python (Join-Path $Root 'find_free_port.py') 8501 2>$null | Out-String).Trim()
if (-not $port) {
    Write-Host '[ERRO] Nenhuma porta livre a partir de 8501.' -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Abrindo http://localhost:$port ..."
Start-Process "http://localhost:$port"
Write-Host 'Pressione Ctrl+C para encerrar.'
Write-Host ''

& $Python -m streamlit run (Join-Path $Root 'app.py') `
    --server.headless true `
    --server.port $port `
    --browser.gatherUsageStats false
exit $LASTEXITCODE
'@
Set-Content -Path (Join-Path $Staging 'Iniciar Parquet Query.ps1') -Value $launcherPs1 -Encoding UTF8

$launcherBat = @'
@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar Parquet Query.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 pause
exit /b %EXIT_CODE%
'@
Set-Content -Path (Join-Path $Staging 'Iniciar Parquet Query.bat') -Value $launcherBat -Encoding Ascii

$repoLine = if ($RepoUrl) { "Projeto: $RepoUrl" } else { 'Projeto: consulte o repositorio no GitHub.' }
$leiaMe = @"
Parquet Query v$Version — Windows 64 bits
=========================================

INICIO RAPIDO
1. Coloque seus arquivos .parquet ou .csv na pasta data\
2. De um duplo clique em "Iniciar Parquet Query.bat"
3. O navegador abrira automaticamente

REQUISITOS
- Windows 10 ou 11 (64 bits)
- Nao e necessario instalar Python

ENCERRAR
- Feche a janela preta do terminal ou pressione Ctrl+C

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

Write-Host ''
Write-Host "Pacote criado: $zipPath"
Write-Host "Pasta staging: $Staging"
