#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$Root = $PSScriptRoot
Set-Location $Root
$Host.UI.RawUI.WindowTitle = 'Parquet Query'

function Write-Banner {
    Write-Host ''
    Write-Host ' Parquet Query'
    Write-Host ' ============='
    Write-Host ''
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Comando falhou com codigo ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
    }
}

function Get-PythonLauncher {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = 'py'; Prefix = @('-3') }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = 'python'; Prefix = @() }
    }
    return $null
}

function Invoke-Python {
    param(
        [hashtable]$Launcher,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $allArgs = @($Launcher.Prefix + $Arguments)
    & $Launcher.Exe @allArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python falhou com codigo $LASTEXITCODE"
    }
}

function Exit-WithError {
    param([string]$Message)

    Write-Host "[ERRO] $Message" -ForegroundColor Red
    exit 1
}

try {
    Write-Banner

    if (-not (Test-Path 'app.py')) {
        Exit-WithError 'app.py nao encontrado. Execute este script na raiz do projeto.'
    }

    if (-not (Test-Path 'requirements.txt')) {
        Exit-WithError 'requirements.txt nao encontrado.'
    }

    $launcher = Get-PythonLauncher
    if (-not $launcher) {
        Exit-WithError ((@(
            'Python 3 nao encontrado.',
            'Instale em https://www.python.org/downloads/ e marque "Add to PATH".'
        ) -join "`n       "))
    }

    try {
        Invoke-Python $launcher '-c' 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'
    } catch {
        $version = & $launcher.Exe @($launcher.Prefix + @('--version')) 2>$null
        if ($version) { Write-Host $version }
        Exit-WithError 'Python 3.9 ou superior e necessario.'
    }

    $version = (& $launcher.Exe @($launcher.Prefix + @('--version')) 2>&1 | Out-String).Trim()
    Write-Host "Python: $version"

    $venvPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Host ''
        Write-Host 'Criando ambiente virtual em .venv ...'
        Invoke-Python $launcher '-m' 'venv' '.venv'
    }

    Write-Host ''
    Write-Host 'Instalando dependencias ...'
    Invoke-Checked $venvPython '-m' 'pip' 'install' '--upgrade' 'pip' '-q'
    Invoke-Checked $venvPython '-m' 'pip' 'install' '-r' 'requirements.txt' '-q'

    if (-not (Test-Path 'data')) {
        Write-Host 'Criando pasta data\ ...'
        New-Item -ItemType Directory -Path 'data' | Out-Null
    }

    $requestedPort = if ($env:STREAMLIT_SERVER_PORT) { $env:STREAMLIT_SERVER_PORT } else { '8501' }
    $port = (& $venvPython 'find_free_port.py' $requestedPort 2>$null | Out-String).Trim()
    if (-not $port) {
        Exit-WithError "Nenhuma porta livre a partir de $requestedPort."
    }

    Write-Host ''
    if ($port -ne $requestedPort) {
        Write-Host "Porta $requestedPort em uso; usando $port."
        Write-Host ''
    }
    Write-Host "Abrindo em http://localhost:$port"
    Write-Host 'Pressione Ctrl+C para encerrar.'
    Write-Host ''

    & $venvPython '-m' 'streamlit' 'run' 'app.py' '--server.headless' 'true' '--server.port' $port
    exit $LASTEXITCODE
} catch {
    Exit-WithError $_.Exception.Message
}
