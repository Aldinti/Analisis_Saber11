<#
.SYNOPSIS
    Tareas de operación del proyecto Análisis Saber 11 (fase F11 del plan).

.DESCRIPTION
    Punto de entrada único para preparar el entorno, ejecutar el pipeline y verificar el
    repositorio, sin tener que recordar rutas ni variables. Todas las tareas usan el
    intérprete de .venv y fijan PYTHONPATH=src, porque el paquete no se instala.

.EXAMPLE
    .\tasks.ps1 setup          # crea .venv, instala dependencias y prepara .env
    .\tasks.ps1 run            # cadena completa: validate-source -> ... -> fairness
    .\tasks.ps1 run -From gold # desde una etapa en adelante
    .\tasks.ps1 run -Stage ml  # una sola etapa
    .\tasks.ps1 test           # pytest con cobertura
    .\tasks.ps1 lint           # ruff
    .\tasks.ps1 clean-tmp      # borra los temporales de DuckDB
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'run', 'test', 'lint', 'clean-tmp', 'help')]
    [string]$Task = 'help',

    [ValidateSet('bronze', 'silver', 'dq', 'gold', 'ml', 'shap', 'fairness')]
    [string]$Stage,

    [ValidateSet('validate-source', 'bronze', 'silver', 'dq-silver', 'gold', 'dq-gold', 'ml', 'shap', 'fairness')]
    [string]$From,

    [ValidateSet('silver', 'gold')]
    [string]$Layer = 'silver'
)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$python = Join-Path $raiz '.venv\Scripts\python.exe'
$env:PYTHONPATH = 'src'

function Assert-Venv {
    if (-not (Test-Path $python)) {
        throw "No existe $python. Ejecute primero: .\tasks.ps1 setup"
    }
}

function Invoke-Python {
    param([string[]]$Argumentos)
    Assert-Venv
    & $python @Argumentos
    return $LASTEXITCODE
}

function Invoke-Setup {
    if (-not (Test-Path $python)) {
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            uv venv --python 3.12 (Join-Path $raiz '.venv')
        }
        else {
            Write-Host 'uv no está disponible; se usa el módulo venv de Python 3.12.'
            py -3.12 -m venv (Join-Path $raiz '.venv')
        }
    }
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r (Join-Path $raiz 'requirements.txt')

    $env_ = Join-Path $raiz '.env'
    if (-not (Test-Path $env_)) {
        Copy-Item (Join-Path $raiz '.env.example') $env_
        $clave = & $python -c "import secrets; print(secrets.token_hex(32))"
        (Get-Content $env_) -replace '^SABER11_HMAC_KEY=.*', "SABER11_HMAC_KEY=$clave" |
            Set-Content $env_ -Encoding utf8
        Write-Host 'Creado .env con una clave HMAC nueva. Respáldela fuera del repositorio:'
        Write-Host '  si se pierde, los seudónimos de cargas anteriores dejan de ser comparables.'
    }
    Write-Host 'Entorno listo.'
    return 0
}

function Invoke-Run {
    $argumentos = @('-m', 'saber11.pipeline', 'run')
    if ($Stage) {
        $argumentos += @('--stage', $Stage)
        if ($Stage -eq 'dq') { $argumentos += @('--layer', $Layer) }
    }
    elseif ($From) {
        $argumentos += @('--from', $From)
    }
    return Invoke-Python $argumentos
}

function Show-Help {
    Get-Help $PSCommandPath -Detailed | Out-String | Write-Host
    return 0
}

switch ($Task) {
    'setup' { $codigo = Invoke-Setup }
    'run' { $codigo = Invoke-Run }
    'test' { $codigo = Invoke-Python @('-m', 'pytest') }
    'lint' { $codigo = Invoke-Python @('-m', 'ruff', 'check', 'src', 'tests', 'scripts') }
    'clean-tmp' {
        $tmp = Join-Path $raiz 'data\_tmp'
        if (Test-Path $tmp) { Remove-Item "$tmp\*" -Recurse -Force -ErrorAction SilentlyContinue }
        Write-Host "Temporales limpiados: $tmp"
        $codigo = 0
    }
    default { $codigo = Show-Help }
}

exit $codigo
