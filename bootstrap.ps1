# Instalacion y ejecucion sin requisitos previos de Python o uv.
# Solo el primer inicio (o un cambio de dependencias) necesita Internet.
param([switch]$SetupOnly)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$localUv = Join-Path $PSScriptRoot '.tools\uv\uv.exe'

try {
    if (Test-Path -LiteralPath $localUv) {
        $uv = $localUv
    } else {
        $cmd = Get-Command uv.exe -ErrorAction SilentlyContinue
        if ($cmd) {
            $uv = $cmd.Source
        } else {
            Write-Host '[1/3] uv no esta instalado. Descargando el instalador oficial de Astral...' -ForegroundColor Cyan
            # Instalacion aislada en esta carpeta; no modifica el PATH del usuario.
            $env:UV_UNMANAGED_INSTALL = Join-Path $PSScriptRoot '.tools\uv'
            $installer = Invoke-RestMethod -Uri 'https://astral.sh/uv/install.ps1' -UseBasicParsing
            Invoke-Expression $installer
            if (-not (Test-Path -LiteralPath $localUv)) {
                throw 'El instalador de uv no genero .tools\uv\uv.exe.'
            }
            $uv = $localUv
        }
    }

    Write-Host '[2/3] Sincronizando el entorno virtual con uv...' -ForegroundColor Cyan
    # uv obtiene Python 3.12 si es necesario y crea o actualiza .venv.
    & $uv sync --python 3.12
    if ($LASTEXITCODE -ne 0) { throw "uv sync ha fallado (codigo $LASTEXITCODE)." }

    if ($SetupOnly) {
        Write-Host 'Entorno listo.' -ForegroundColor Green
        exit 0
    }

    Write-Host '[3/3] Ejecutando KeePass LAN Share...' -ForegroundColor Green
    & $uv run --no-sync --python 3.12 python app.py
    if ($LASTEXITCODE -ne 0) { throw "La aplicacion termino con codigo $LASTEXITCODE." }
} catch {
    Write-Host ("ERROR: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'La primera instalacion necesita Internet y acceso a los repositorios de Python.' -ForegroundColor Yellow
    exit 1
}
