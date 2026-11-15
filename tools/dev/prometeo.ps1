# PROMETEO - local stack manager for Windows (Windows PowerShell 5.1+ / PowerShell 7).
#
# Normally you do not run this file directly: double-click one of the launchers in the repo root
#   start-prometeo.bat   daily start (Postgres if needed, API :8000, web :3000, opens the browser)
#   init-prometeo.bat    first-time setup (dependencies, .env, database, data validation)
#   prometeo.bat         menu (start, setup, knowledge base, status, stop)
#
# Safety rules this script follows:
#   - never prints API keys or passwords (only "set" / "not set");
#   - never deletes containers, volumes, databases, .env files or documents;
#   - never kills a process that does not belong to this repository;
#   - never rebuilds the knowledge base unless explicitly asked.
# Messages are plain ASCII so they render in any Windows console code page.

[CmdletBinding()]
param(
    [ValidateSet('menu', 'start', 'setup', 'kb', 'status', 'stop')]
    [string]$Action = 'menu',
    [switch]$SetupOnly,      # setup: do not launch API/web afterwards
    [switch]$WithKnowledge,  # setup: also install knowledge-base Python packages
    [switch]$BuildKb,        # setup: also build the knowledge base if it is empty
    [switch]$RebuildKb,      # kb: rebuild/update even if the knowledge base has documents
    [ValidateSet('ask', 'bass2', 'all')]
    [string]$Scope = 'ask',  # kb: bass2 = BASS-II only (PSI-25, fast) | all = every combustion study
    [switch]$NoBrowser,      # start: do not open http://localhost:3000
    [switch]$StopDb          # stop: also stop the Postgres container (data is kept)
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Backend = Join-Path $Root 'apps\backend'
$Frontend = Join-Path $Root 'apps\frontend'
$EnvFile = Join-Path $Root '.env'
$DevCheck = Join-Path $Root 'tools\dev\devcheck.py'
$ApiPort = 8000
$WebPort = 3000
$ApiTitle = 'Prometeo API :8000'
$WebTitle = 'Prometeo Web :3000'
Set-Location -LiteralPath $Root

# ----------------------------- output helpers -----------------------------

function Say([string]$Text) { Write-Host $Text }
function Step([string]$Text) { Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Ok([string]$Text) { Write-Host "  [OK]    $Text" -ForegroundColor Green }
function Info([string]$Text) { Write-Host "  [INFO]  $Text" }
function Warn([string]$Text) { Write-Host "  [AVISO] $Text" -ForegroundColor Yellow }
function Fail([string]$Text) { Write-Host "  [ERROR] $Text" -ForegroundColor Red }

function Ask-YesNo([string]$Question) {
    $answer = Read-Host "  $Question [s/N]"
    return ($answer -match '^(s|si|y|yes)$')
}

# ----------------------------- configuration -----------------------------

function Read-DotEnv([string]$Path) {
    # Last assignment wins, like pydantic-settings and docker compose.
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $values }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $value = $Matches[2]
            if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") { $value = $Matches[1] }
            elseif ($value -match '^(.*?)\s+#') { $value = $Matches[1] }
            $values[$Matches[1]] = $value
        }
    }
    return $values
}

function Get-Setting($Config, [string]$Name, [string]$Default) {
    if ($Config.ContainsKey($Name) -and $Config[$Name] -ne '') { return $Config[$Name] }
    return $Default
}

function Get-Config {
    $envValues = Read-DotEnv $EnvFile
    return [pscustomobject]@{
        PgPort        = [int](Get-Setting $envValues 'POSTGRES_PORT' '5432')
        DocumentStore = Get-Setting $envValues 'PROMETEO_DOCUMENT_STORE' 'json'
        TrialStore    = Get-Setting $envValues 'PROMETEO_TRIAL_STORE' 'json'
        Explainer     = Get-Setting $envValues 'PROMETEO_EXPLAINER' 'offline'
        DatabaseUrl   = Get-Setting $envValues 'PROMETEO_DATABASE_URL' 'postgresql://prometeo:prometeo@localhost:5432/prometeo'
    }
}

function Test-DbNeeded($Config) {
    return ($Config.DocumentStore -eq 'postgres' -or $Config.TrialStore -eq 'postgres')
}

function Test-DbIsLocal($Config) {
    return ($Config.DatabaseUrl -match '@(localhost|127\.0\.0\.1|\[::1\])(:|/)')
}

# ----------------------------- tools -----------------------------

$script:PnpmCmd = $null

function Resolve-Pnpm {
    if ($script:PnpmCmd) { return $script:PnpmCmd }
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        $script:PnpmCmd = 'pnpm'
    }
    elseif (Get-Command corepack -ErrorAction SilentlyContinue) {
        # Corepack ships with Node and runs the pnpm version pinned in package.json.
        $env:COREPACK_ENABLE_DOWNLOAD_PROMPT = '0'
        $script:PnpmCmd = 'corepack pnpm'
    }
    return $script:PnpmCmd
}

function Invoke-Pnpm([string[]]$Arguments) {
    $cmd = Resolve-Pnpm
    if ($cmd -eq 'pnpm') { & pnpm @Arguments | Out-Host } else { & corepack pnpm @Arguments | Out-Host }
    return $LASTEXITCODE
}

function Test-Prerequisites([switch]$Quiet) {
    $okAll = $true
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Fail 'Node.js no esta instalado. Instala Node 22 LTS: https://nodejs.org  (o: winget install OpenJS.NodeJS.LTS)'
        $okAll = $false
    }
    else {
        $version = (& node -v) -replace '^v', ''
        if ([int]($version.Split('.')[0]) -lt 22) { Fail "Node $version es demasiado antiguo; se necesita 22 o superior."; $okAll = $false }
        elseif (-not $Quiet) { Ok "Node $version" }
    }
    $pnpm = Resolve-Pnpm
    if (-not $pnpm) { Fail 'pnpm no encontrado. Ejecuta: npm install -g pnpm@11'; $okAll = $false }
    elseif (-not $Quiet) { Ok "pnpm (via '$pnpm')" }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail 'uv (gestor de Python) no esta instalado. Instala: winget install astral-sh.uv  y abre una ventana nueva.'
        $okAll = $false
    }
    elseif (-not $Quiet) { Ok ((& uv --version) -join ' ') }
    return $okAll
}

# ----------------------------- ports & processes -----------------------------

function Get-ListenerPid([int]$Port) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    return $null
}

function Get-CommandLine([int]$ProcessId) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($proc) { return [string]$proc.CommandLine }
    return ''
}

function Test-ProjectProcess([int]$ProcessId) {
    # A process belongs to Prometeo only if its command line runs something inside this repo.
    $cmdLine = Get-CommandLine $ProcessId
    return ($cmdLine -and $cmdLine.ToLower().Contains($Root.ToLower()))
}

function Get-ProcessLabel([int]$ProcessId) {
    $p = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($p) { return "$($p.ProcessName) (PID $ProcessId)" }
    return "PID $ProcessId"
}

function Invoke-Http([string]$Url, [int]$TimeoutSec = 3) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $r
    }
    catch {
        if ($_.Exception.Response) { return $_.Exception.Response }
        return $null
    }
}

function Test-ApiHealthy {
    $r = Invoke-Http "http://127.0.0.1:$ApiPort/health"
    return ($r -and [int]$r.StatusCode -eq 200)
}

function Test-WebUp {
    $r = Invoke-Http "http://localhost:$WebPort/" 10
    return ($r -and [int]$r.StatusCode -lt 500)
}

function Find-FreePort([int]$From) {
    for ($p = $From; $p -lt $From + 20; $p++) { if (-not (Get-ListenerPid $p)) { return $p } }
    return $null
}

# ----------------------------- Docker & Postgres -----------------------------

function Test-DockerDaemon {
    & docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail 'Docker no esta instalado. Instala Docker Desktop: https://www.docker.com/products/docker-desktop/'
        return $false
    }
    if (Test-DockerDaemon) { Ok 'Docker Desktop esta funcionando'; return $true }
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        Fail 'Docker no responde. Abre Docker Desktop manualmente y vuelve a intentarlo.'
        return $false
    }
    Info 'Docker Desktop esta apagado; abriendolo (puede tardar 1-2 minutos)...'
    Start-Process -FilePath $exe | Out-Null
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        if (Test-DockerDaemon) { Ok 'Docker Desktop listo'; return $true }
    }
    Fail 'Docker Desktop no termino de arrancar. Abrelo, espera a que diga "Engine running" y reintenta.'
    return $false
}

function Get-DbContainerId {
    $id = (& docker compose ps -q db 2>$null | Select-Object -First 1)
    if ($id) { return $id.Trim() }
    return $null
}

function Get-DbPublishedPort {
    $mapping = (& docker compose port db 5432 2>$null | Select-Object -First 1)
    if ($mapping -and $mapping -match ':(\d+)\s*$') { return [int]$Matches[1] }
    return $null
}

function Get-DbHealth {
    $id = Get-DbContainerId
    if (-not $id) { return 'stopped' }
    $state = (& docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}' $id 2>$null)
    if (-not $state) { return 'unknown' }
    return [string]$state
}

function Ensure-Postgres($Config, [bool]$Required) {
    if (-not (Test-DbIsLocal $Config)) {
        Info 'PROMETEO_DATABASE_URL apunta a un servidor externo (no localhost): no se usa Docker.'
        return $true
    }
    if (-not (Ensure-Docker)) { return (-not $Required) }

    $port = $Config.PgPort
    $published = Get-DbPublishedPort
    if ($published -eq $port -and (Get-DbHealth) -eq 'running/healthy') {
        Ok "PostgreSQL de Prometeo ya esta encendido (puerto $port)"
        return $true
    }

    # Port taken by something that is not Prometeo's container -> never touch it.
    $listener = Get-ListenerPid $port
    if ($listener -and $published -ne $port) {
        Fail "El puerto $port ya lo usa otro programa: $(Get-ProcessLabel $listener)."
        Say  "         Prometeo no lo cerrara ni se conectara a esa otra base de datos."
        $free = Find-FreePort ($port + 1)
        if ($free) {
            Say  "         Solucion: en .env pon el mismo puerto libre en ambas lineas, por ejemplo:"
            Say  "           POSTGRES_PORT=$free"
            Say  "           PROMETEO_DATABASE_URL=postgresql://prometeo:<password>@localhost:$free/prometeo"
        }
        return (-not $Required)
    }

    if ($published -and $published -ne $port) {
        Info "El contenedor estaba publicado en el puerto $published; .env pide $port. Se recrea (los datos se conservan)."
    }
    Info 'Encendiendo PostgreSQL + pgvector (docker compose up -d db)...'
    & docker compose up -d --quiet-pull db | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Fail 'docker compose no pudo encender la base de datos (mira el mensaje de arriba).'
        return (-not $Required)
    }
    for ($i = 0; $i -lt 40; $i++) {
        if ((Get-DbHealth) -eq 'running/healthy') { Ok "PostgreSQL listo en localhost:$port"; return $true }
        Start-Sleep -Seconds 2
    }
    Fail 'PostgreSQL no paso a "healthy" a tiempo. Revisa: docker compose logs db'
    return (-not $Required)
}

function Show-DbStatus($Config) {
    # Read-only; retries briefly because a brand-new volume applies migrations right after start.
    for ($attempt = 0; $attempt -lt 6; $attempt++) {
        $out = Invoke-DevCheckCapture @('db')
        if ($out.Code -ne 10 -and $out.Code -ne 12) { break }
        Start-Sleep -Seconds 3
    }
    $out.Lines | ForEach-Object { Say "         $_" }
    switch ($out.Code) {
        0 { Ok 'Base de datos y esquema correctos' }
        10 { Fail 'Base de datos apagada o puerto equivocado.' }
        11 { Fail 'Credenciales o nombre de base incorrectos.' }
        12 { Fail 'Tablas/migraciones incompletas (ver arriba). No se ha modificado nada.' }
        13 { Warn 'La Knowledge Base esta vacia: el Research Assistant no encontrara documentos. Usa la opcion 3 del menu (prometeo.bat).' }
        default { Fail "Comprobacion de base de datos fallo (codigo $($out.Code))." }
    }
    return $out
}

function Invoke-DevCheckCapture([string[]]$Arguments) {
    $lines = & uv run --no-sync --project $Backend python $DevCheck @Arguments 2>&1 | ForEach-Object { "$_" }
    return [pscustomobject]@{ Code = $LASTEXITCODE; Lines = @($lines) }
}

# ----------------------------- dependencies -----------------------------

function Test-KnowledgeInstalled {
    $py = Join-Path $Backend '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { return $false }
    & $py -c "import fastembed, pypdf" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Sync-Python([bool]$Knowledge) {
    # --inexact: never uninstall packages that are already there (e.g. knowledge/vision extras).
    $uvArgs = @('sync', '--inexact')
    if ($Knowledge) { $uvArgs += @('--extra', 'knowledge') }
    Info ("uv " + ($uvArgs -join ' ') + "   (apps\backend)")
    Push-Location -LiteralPath $Backend
    & uv @uvArgs | Out-Host
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Fail 'uv sync fallo (mira el mensaje de arriba).'; return $false }
    Ok 'Entorno Python listo'
    return $true
}

function Install-Js {
    Info 'pnpm install'
    if ((Invoke-Pnpm @('install')) -ne 0) { Fail 'pnpm install fallo (mira el mensaje de arriba).'; return $false }
    Ok 'Dependencias JavaScript listas'
    return $true
}

function Test-JsStale {
    $marker = Join-Path $Root 'node_modules\.modules.yaml'
    if (-not (Test-Path -LiteralPath $marker)) { return $true }
    $lock = Get-Item -LiteralPath (Join-Path $Root 'pnpm-lock.yaml')
    return ($lock.LastWriteTime -gt (Get-Item -LiteralPath $marker).LastWriteTime)
}

function Test-PythonStale {
    $venvCfg = Join-Path $Backend '.venv\pyvenv.cfg'
    return (-not (Test-Path -LiteralPath $venvCfg))
}

function Ensure-Dependencies($Config) {
    # Daily start: install only what is missing or out of date.
    if (Test-JsStale) {
        Info 'Faltan dependencias JavaScript o pnpm-lock.yaml cambio.'
        if (-not (Install-Js)) { return $false }
    }
    else { Ok 'Dependencias JavaScript al dia' }
    $needKnowledge = ($Config.DocumentStore -eq 'postgres')
    if (Test-PythonStale) {
        Info 'El entorno Python no existe todavia.'
        if (-not (Sync-Python $needKnowledge)) { return $false }
    }
    elseif ($needKnowledge -and -not (Test-KnowledgeInstalled)) {
        Info 'PROMETEO_DOCUMENT_STORE=postgres necesita los paquetes de Knowledge Base.'
        if (-not (Sync-Python $true)) { return $false }
    }
    else { Ok 'Entorno Python presente' }
    return $true
}

# ----------------------------- .env -----------------------------

function Ensure-EnvFile {
    if (Test-Path -LiteralPath $EnvFile) {
        Ok '.env encontrado en la raiz (no se modifica)'
    }
    else {
        $example = Join-Path $Root '.env.example'
        if (-not (Test-Path -LiteralPath $example)) { Fail 'Falta .env.example'; return $false }
        Copy-Item -LiteralPath $example -Destination $EnvFile
        Ok '.env creado a partir de .env.example (valores por defecto, modo offline)'
    }
    if (Test-Path -LiteralPath (Join-Path $Backend '.env')) {
        Warn 'apps\backend\.env existe y SOBRESCRIBE la .env de la raiz. Pasa sus valores a la .env raiz y borralo.'
    }
    return $true
}

function Check-Env([switch]$OfferMerge) {
    $out = Invoke-DevCheckCapture @('env')
    $show = $out.Lines | Where-Object { $_ -match '\[(WARN|ERROR)\]|^\s{2,}\S' -and $_ -notmatch '^\s{2}(PROMETEO_|POSTGRES_|ANTHROPIC_)' }
    $show | ForEach-Object { Say "         $_" }
    if ($out.Code -ne 0) { Fail '.env tiene configuraciones contradictorias (ver arriba). Corrigelas y vuelve a ejecutar.'; return $false }
    $hasLocal = ($out.Lines -join "`n") -match '\.env\.local is NOT read'
    if ($hasLocal -and $OfferMerge) {
        if (Ask-YesNo 'Copiar esos valores de .env.local a .env? (se guarda un backup de .env)') {
            & uv run --no-sync --project $Backend python $DevCheck merge-local --yes | Out-Host
        }
    }
    if (-not $hasLocal) { Ok '.env coherente' }
    return $true
}

function Show-ConfigSummary($Config) {
    $envValues = Read-DotEnv $EnvFile
    $key = if (Get-Setting $envValues 'ANTHROPIC_API_KEY' '') { 'configurada' } else { 'NO configurada' }
    Info ("Documentos: {0} | Ensayos: {1} | IA: {2} (ANTHROPIC_API_KEY {3}) | Postgres: puerto {4}" -f `
            $Config.DocumentStore, $Config.TrialStore, $Config.Explainer, $key, $Config.PgPort)
}

# ----------------------------- API & web -----------------------------

function Start-Window([string]$Title, [string]$WorkDir, [string]$Command) {
    # A visible console per service: closing it stops that service; errors stay on screen.
    $line = "title $Title & echo $Title - cierra esta ventana para detenerlo. & $Command"
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $line -WorkingDirectory $WorkDir | Out-Null
}

function Ensure-Service([string]$Name, [int]$Port, [scriptblock]$IsUp, [string]$Title, [string]$WorkDir, [string]$Command) {
    $listener = Get-ListenerPid $Port
    if ($listener) {
        if (-not (Test-ProjectProcess $listener)) {
            Fail "El puerto $Port lo usa otro programa: $(Get-ProcessLabel $listener). No se toca."
            Say  "         Cierra ese programa o liberalo, y vuelve a ejecutar start-prometeo.bat."
            return 'blocked'
        }
        if (& $IsUp) {
            $started = (Get-Process -Id $listener -ErrorAction SilentlyContinue).StartTime
            Ok "$Name ya esta funcionando en el puerto $Port (no se duplica)"
            if ($started -and (Get-Item -LiteralPath $EnvFile).LastWriteTime -gt $started) {
                Warn "$Name arranco ANTES del ultimo cambio en .env; para aplicar el cambio: prometeo.bat -> Detener, y luego Iniciar."
            }
            return 'running'
        }
        Info "$Name (proceso de Prometeo) ya esta arrancando en el puerto $Port; se espera."
        return 'starting'
    }
    Info "Iniciando $Name en una ventana nueva ('$Title')..."
    Start-Window $Title $WorkDir $Command
    return 'started'
}

function Wait-Until([scriptblock]$Probe, [int]$Seconds, [string]$Label) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Probe) { return $true }
        Start-Sleep -Seconds 2
    }
    Fail "$Label no respondio en $Seconds s. Mira su ventana para ver el error."
    return $false
}

function Show-ApiChecks {
    $base = "http://127.0.0.1:$ApiPort/api/v1"
    try {
        $trials = Invoke-RestMethod -Uri "$base/trials" -TimeoutSec 20
        Ok ("Explorer: {0} ensayos curados" -f @($trials).Count)
    }
    catch { Fail "GET /api/v1/trials fallo: $($_.Exception.Message)" }
    try {
        # Assign before @(): PowerShell 5.1 emits a JSON array as ONE pipeline object.
        $simList = Invoke-RestMethod -Uri "$base/cfd/simulations" -TimeoutSec 20
        $sims = @($simList)
        $converged = @($sims | Where-Object { $_.convergence_status -eq 'converged' }).Count
        Ok ("CFD Physics Lab: {0} casos ({1} con convergencia confirmada, {2} sin convergencia demostrada)" -f $sims.Count, $converged, ($sims.Count - $converged))
    }
    catch { Fail "GET /api/v1/cfd/simulations fallo: $($_.Exception.Message)" }
    try {
        $models = Invoke-RestMethod -Uri "$base/assistant/models" -TimeoutSec 20
        $ids = @($models.models | ForEach-Object { $_.id })
        if ($ids.Count -gt 0) { Ok ("Research Assistant: modelos Claude -> " + ($ids -join ', ')) }
        else { Info 'Research Assistant: modo offline (sin modelo Claude configurado)' }
    }
    catch { Fail "GET /api/v1/assistant/models fallo: $($_.Exception.Message)" }
}

function Show-Urls {
    Say ''
    Say '  Prometeo:'
    Say "    Web .............. http://localhost:$WebPort"
    Say "    API .............. http://127.0.0.1:$ApiPort/docs   (salud: /health)"
    Say "    Ventanas ......... '$ApiTitle' y '$WebTitle' (cierralas para detener)"
    Say '    PostgreSQL ....... sigue encendido en Docker; prometeo.bat -> Detener lo apaga si quieres'
}

# ----------------------------- actions -----------------------------

function Invoke-Start {
    Step 'Comprobando herramientas'
    if (-not (Test-Prerequisites -Quiet)) { return 1 }
    Ok 'Node, pnpm y uv disponibles'
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Warn 'No hay .env todavia: ejecutando la configuracion inicial primero.'
        return (Invoke-Setup)
    }
    $config = Get-Config

    Step 'Configuracion (.env de la raiz)'
    if (-not (Check-Env)) { return 1 }
    Show-ConfigSummary $config

    Step 'Dependencias'
    if (-not (Ensure-Dependencies $config)) { return 1 }

    Step 'PostgreSQL'
    $dbNeeded = Test-DbNeeded $config
    if (-not $dbNeeded) { Info 'Con PROMETEO_DOCUMENT_STORE=json y PROMETEO_TRIAL_STORE=json la base es opcional.' }
    if (-not (Ensure-Postgres $config $dbNeeded)) { return 1 }
    if ($dbNeeded -or (Get-DbHealth) -eq 'running/healthy') {
        $db = Show-DbStatus $config
        if ($dbNeeded -and $db.Code -ne 0 -and $db.Code -ne 13) { return 1 }
    }

    Step 'API (FastAPI) y web (Next.js)'
    $api = Ensure-Service 'API' $ApiPort { Test-ApiHealthy } $ApiTitle $Backend 'uv run prometeo serve'
    $web = Ensure-Service 'Web' $WebPort { Test-WebUp } $WebTitle $Frontend ((Resolve-Pnpm) + ' dev')
    if ($api -eq 'blocked' -or $web -eq 'blocked') { return 1 }

    $apiOk = Wait-Until { Test-ApiHealthy } 120 'La API'
    if ($apiOk) { Ok "API sana en http://127.0.0.1:$ApiPort/health"; Show-ApiChecks }
    if ($web -ne 'running') { Info 'Esperando a la web (la primera compilacion puede tardar ~1 min)...' }
    $webOk = Wait-Until { Test-WebUp } 240 'La web'
    if ($webOk) { Ok "Web lista en http://localhost:$WebPort" }

    Show-Urls
    if ($apiOk -and $webOk) {
        if (-not $NoBrowser) { Start-Process "http://localhost:$WebPort" | Out-Null }
        return 0
    }
    return 1
}

function Invoke-Setup {
    Step 'Comprobando herramientas'
    if (-not (Test-Prerequisites)) { return 1 }

    Step 'Configuracion (.env unico en la raiz)'
    if (-not (Ensure-EnvFile)) { return 1 }
    if (-not (Check-Env -OfferMerge)) { return 1 }
    $config = Get-Config
    Show-ConfigSummary $config

    Step 'Dependencias JavaScript'
    if (-not (Install-Js)) { return 1 }

    Step 'Dependencias Python'
    $knowledge = ($WithKnowledge -or $BuildKb -or $config.DocumentStore -eq 'postgres' -or (Test-KnowledgeInstalled))
    if (-not (Sync-Python $knowledge)) { return 1 }

    Step 'PostgreSQL + pgvector'
    $dbNeeded = Test-DbNeeded $config
    if (-not (Ensure-Postgres $config $dbNeeded)) { return 1 }
    $db = $null
    if ((Get-DbHealth) -eq 'running/healthy' -or -not (Test-DbIsLocal $config)) { $db = Show-DbStatus $config }

    Step 'Validando datos curados'
    Push-Location -LiteralPath $Backend
    & uv run --no-sync prometeo validate-data | Out-Host
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Fail 'validate-data fallo.'; return 1 }
    Ok 'Datos curados validos'

    if ($BuildKb -and $db -and $db.Code -eq 13) {
        if ((Invoke-Kb) -ne 0) { return 1 }
    }

    Step 'Configuracion inicial completa'
    if ($SetupOnly) { Info 'Modo --setup-only: no se inician la API ni la web.'; return 0 }
    return (Invoke-Start)
}

function Invoke-Kb {
    Step 'Knowledge Base (documentos NASA para el Research Assistant)'
    if (-not (Test-Prerequisites -Quiet)) { return 1 }
    $config = Get-Config
    if (-not (Test-KnowledgeInstalled)) {
        Info 'Instalando los paquetes de Knowledge Base (embeddings + lectura de PDF)...'
        if (-not (Sync-Python $true)) { return 1 }
    }
    else { Ok 'Paquetes de Knowledge Base instalados' }
    if (-not (Ensure-Postgres $config $true)) { return 1 }
    $db = Show-DbStatus $config
    if ($db.Code -ne 0 -and $db.Code -ne 13) { return 1 }

    $chunks = 0
    $text = $db.Lines -join "`n"
    if ($text -match '(\d+) text chunks') { $chunks = [int]$Matches[1] }
    if ($chunks -gt 0 -and -not $RebuildKb) {
        Ok "La Knowledge Base ya tiene $chunks fragmentos indexados."
        Say '         Actualizarla vuelve a consultar NASA PSI (necesita Internet y puede tardar mucho).'
        Say '         No se borra nada: solo se reemplazan los fragmentos de cada documento que se reindexe.'
        if ($Scope -ne 'ask' -or -not (Ask-YesNo 'Actualizar/reconstruir ahora?')) {
            Info 'Sin cambios en la Knowledge Base.'
            return 0
        }
    }

    $selected = $Scope
    if ($selected -eq 'ask') {
        Say ''
        Say '    1) Solo BASS-II (PSI-25) - recomendado para empezar, mas rapido'
        Say '    2) Todos los estudios de combustion de NASA PSI - completo, tarda mas'
        $choice = Read-Host '  Elige 1 o 2 (Enter = 1)'
        $selected = if ($choice -eq '2') { 'all' } else { 'bass2' }
    }
    $kbArgs = @('run', '--extra', 'knowledge', 'prometeo', 'build-knowledge-base')
    if ($selected -eq 'bass2') { $kbArgs += @('--only', 'PSI-25') }
    Info ("Ejecutando: uv " + ($kbArgs -join ' ') + "   (descarga documentos a data\raw\psi)")
    Push-Location -LiteralPath $Backend
    & uv @kbArgs | Out-Host
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Warn 'La construccion termino con errores en algunos documentos (ver arriba). Lo indexado se conserva.' }
    $db = Show-DbStatus $config
    if ($config.DocumentStore -ne 'postgres') {
        Warn 'Tu .env usa PROMETEO_DOCUMENT_STORE=json: el asistente aun NO usa esta Knowledge Base.'
        Say  '         Para usarla pon PROMETEO_DOCUMENT_STORE=postgres en .env y reinicia la API.'
    }
    else { Info 'Si la API ya estaba encendida no hace falta reiniciarla: lee la base en cada pregunta.' }
    if ($db.Code -eq 0) { return 0 }
    return 1
}

function Invoke-Status {
    Step 'Herramientas'
    [void](Test-Prerequisites)
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        if (Test-DockerDaemon) { Ok 'Docker Desktop funcionando' } else { Warn 'Docker Desktop apagado' }
    }
    else { Warn 'Docker no instalado' }

    Step 'Configuracion (.env)'
    if (-not (Test-Path -LiteralPath $EnvFile)) { Fail 'No existe .env: ejecuta init-prometeo.bat'; return 1 }
    [void](Check-Env)
    $config = Get-Config
    Show-ConfigSummary $config
    $deps = Invoke-DevCheckCapture @('deps')
    $deps.Lines | ForEach-Object { Say "         $_" }

    Step 'PostgreSQL'
    if (Test-DbIsLocal $config) {
        $health = Get-DbHealth
        $published = Get-DbPublishedPort
        Info "Contenedor db: $health$(if ($published) { ", publicado en localhost:$published" })"
        if ($published -and $published -ne $config.PgPort) { Warn "El contenedor usa el puerto $published pero .env dice $($config.PgPort)." }
    }
    [void](Show-DbStatus $config)

    Step 'Servicios'
    foreach ($svc in @(@{ Name = 'API'; Port = $ApiPort; Up = { Test-ApiHealthy } }, @{ Name = 'Web'; Port = $WebPort; Up = { Test-WebUp } })) {
        $listener = Get-ListenerPid $svc.Port
        if (-not $listener) { Info "$($svc.Name): apagada (puerto $($svc.Port) libre)"; continue }
        if (-not (Test-ProjectProcess $listener)) { Warn "$($svc.Name): el puerto $($svc.Port) lo usa otro programa: $(Get-ProcessLabel $listener)"; continue }
        if (& $svc.Up) { Ok "$($svc.Name): funcionando en el puerto $($svc.Port)" } else { Warn "$($svc.Name): proceso presente pero aun no responde" }
    }
    if (Test-ApiHealthy) { Show-ApiChecks }
    return 0
}

function Stop-ProjectTree([int]$ProcessId) {
    # Walk up to the console window that hosts the service, as long as it is ours, then kill the tree.
    $target = $ProcessId
    for ($i = 0; $i -lt 6; $i++) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$target" -ErrorAction SilentlyContinue
        if (-not $proc) { break }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
        if (-not $parent) { break }
        # Climb only through runner processes (uv/node/python) and the console window this
        # script opened (its command line carries the 'Prometeo API :' / 'Prometeo Web :' title).
        # Never climb into a user's own terminal, editor or explorer.
        $name = ([string]$parent.Name).ToLower()
        $isOurs = $false
        if ($name -eq 'cmd.exe') { $isOurs = ([string]$parent.CommandLine) -match 'Prometeo (API|Web) :' }
        elseif ($name -in @('uv.exe', 'node.exe', 'python.exe', 'prometeo.exe', 'uvicorn.exe')) { $isOurs = $true }
        if (-not $isOurs) { break }
        $target = [int]$parent.ProcessId
    }
    & taskkill /PID $target /T /F *> $null
}

function Invoke-Stop {
    Step 'Deteniendo API y web de Prometeo'
    foreach ($svc in @(@{ Name = 'API'; Port = $ApiPort }, @{ Name = 'Web'; Port = $WebPort })) {
        $listener = Get-ListenerPid $svc.Port
        if (-not $listener) { Info "$($svc.Name): ya estaba apagada"; continue }
        if (-not (Test-ProjectProcess $listener)) {
            Warn "$($svc.Name): el puerto $($svc.Port) es de otro programa ($(Get-ProcessLabel $listener)); no se toca."
            continue
        }
        Stop-ProjectTree $listener
        Start-Sleep -Seconds 1
        if (Get-ListenerPid $svc.Port) { Warn "$($svc.Name): sigue activa; cierra su ventana manualmente." }
        else { Ok "$($svc.Name) detenida" }
    }
    if ($StopDb -or ((Get-DbContainerId) -and (Ask-YesNo 'Apagar tambien PostgreSQL? (docker compose stop db; NO borra datos)'))) {
        & docker compose stop db | Out-Host
        Ok 'PostgreSQL detenido (los datos siguen en el volumen de Docker)'
    }
    return 0
}

function Invoke-Menu {
    while ($true) {
        Say ''
        Say '  ============================================'
        Say '   PROMETEO - Scientific Intelligence for Fire'
        Say '   Safety in Space  |  menu local'
        Say '  ============================================'
        Say '   1. Iniciar Prometeo'
        Say '   2. Configuracion inicial (primera vez / tras git pull)'
        Say '   3. Preparar Knowledge Base (documentos NASA)'
        Say '   4. Verificar servicios'
        Say '   5. Detener API y web'
        Say '   6. Salir'
        $choice = Read-Host '  Opcion'
        switch ($choice) {
            '1' { [void](Invoke-Start) }
            '2' { [void](Invoke-Setup) }
            '3' { [void](Invoke-Kb) }
            '4' { [void](Invoke-Status) }
            '5' { [void](Invoke-Stop) }
            '6' { return 0 }
            default { Warn 'Opcion no valida' }
        }
    }
}

switch ($Action) {
    'menu' { $result = Invoke-Menu }
    'start' { $result = Invoke-Start }
    'setup' { $result = Invoke-Setup }
    'kb' { $result = Invoke-Kb }
    'status' { $result = Invoke-Status }
    'stop' { $result = Invoke-Stop }
}
exit ([int]($result | Select-Object -Last 1))
