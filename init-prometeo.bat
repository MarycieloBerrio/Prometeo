@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM  PROMETEO — Windows one-shot initializer
REM  Sets up env, installs deps, starts Postgres (Docker), then launches
REM  Evidence Engine API (:8000) and Next.js frontend (:3000).
REM
REM  Usage (from repo root):
REM    init-prometeo.bat
REM    init-prometeo.bat --setup-only
REM    init-prometeo.bat --with-knowledge
REM ============================================================================

cd /d "%~dp0"
set "ROOT=%CD%"
set "SETUP_ONLY=0"
set "WITH_KNOWLEDGE=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--setup-only" set "SETUP_ONLY=1"
if /I "%~1"=="--with-knowledge" set "WITH_KNOWLEDGE=1"
if /I "%~1"=="-h" goto usage
if /I "%~1"=="--help" goto usage
shift
goto parse_args

:usage
echo.
echo  init-prometeo.bat [--setup-only] [--with-knowledge]
echo.
echo    --setup-only       Install deps + start DB; do not open API/web windows
echo    --with-knowledge   Also uv sync --extra knowledge (for pnpm kb:build later)
echo.
exit /b 0

:args_done
echo.
echo ============================================================
echo  PROMETEO init  ^|  %ROOT%
echo ============================================================
echo.

REM ---- Prerequisites -------------------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. Install Node ^>= 22 and reopen the terminal.
  exit /b 1
)
where pnpm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] pnpm not found. Install with:  npm install -g pnpm@11
  exit /b 1
)
where uv >nul 2>&1
if errorlevel 1 (
  echo [ERROR] uv not found. Install from https://docs.astral.sh/uv/ and reopen the terminal.
  exit /b 1
)
where docker >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker not found. Install Docker Desktop and ensure it is running.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker daemon is not reachable. Start Docker Desktop and retry.
  exit /b 1
)

REM ---- .env ----------------------------------------------------------------
if not exist "%ROOT%\.env" (
  if exist "%ROOT%\.env.example" (
    echo [1/6] Creating .env from .env.example
    copy /Y "%ROOT%\.env.example" "%ROOT%\.env" >nul
  ) else (
    echo [WARN] No .env.example found; continuing with process defaults
  )
) else (
  echo [1/6] .env already present — leaving it untouched
)

REM The API reads the repo-root .env directly. A copy in apps\backend\.env would override it,
REM so later edits to the root file would seem to have no effect.
if exist "%ROOT%\apps\backend\.env" (
  echo [WARN] apps\backend\.env exists and overrides the repo-root .env.
  echo        Move its settings into the root .env and delete it.
)

REM ---- JS workspace --------------------------------------------------------
echo [2/6] pnpm install
call pnpm install
if errorlevel 1 (
  echo [ERROR] pnpm install failed
  exit /b 1
)

REM ---- Python backend ------------------------------------------------------
echo [3/6] uv sync ^(apps\backend^)
pushd "%ROOT%\apps\backend"
if "%WITH_KNOWLEDGE%"=="1" (
  call uv sync --extra knowledge
) else (
  call uv sync
)
if errorlevel 1 (
  popd
  echo [ERROR] uv sync failed
  exit /b 1
)
popd

REM ---- Database ------------------------------------------------------------
echo [4/6] Starting Postgres + pgvector ^(docker compose^)
call pnpm db:up
if errorlevel 1 (
  echo [ERROR] pnpm db:up failed
  exit /b 1
)

echo       Waiting for Postgres to accept connections...
set "DB_READY=0"
for /L %%i in (1,1,30) do (
  docker compose exec -T db pg_isready -U prometeo >nul 2>&1
  if not errorlevel 1 (
    set "DB_READY=1"
    goto db_ready
  )
  timeout /t 2 /nobreak >nul
)

:db_ready
if "%DB_READY%"=="0" (
  echo [WARN] pg_isready timed out — container may still be initializing
) else (
  echo       Postgres is ready
)

echo [5/6] Database diagnose + curated data validate
pushd "%ROOT%\apps\backend"
call uv run prometeo diagnose-db
if errorlevel 1 (
  echo [WARN] diagnose-db reported issues ^(fresh volume may still be applying migrations^)
)
call uv run prometeo validate-data
if errorlevel 1 (
  popd
  echo [ERROR] validate-data failed
  exit /b 1
)
popd

echo [6/6] Setup complete
echo.
echo   API docs will be at  http://127.0.0.1:8000/docs
echo   Web app will be at   http://localhost:3000
echo   Postgres:            localhost:5432  ^(user/db: prometeo^)
echo.
echo   Optional later:
echo     pnpm kb:build              ^(needs: init-prometeo.bat --with-knowledge^)
echo     set PROMETEO_DOCUMENT_STORE=postgres in .env to search the KB
echo.

if "%SETUP_ONLY%"=="1" (
  echo Setup-only mode: not starting API/web.
  exit /b 0
)

REM ---- Launch API + frontend in new consoles -------------------------------
echo Starting Evidence Engine API in a new window...
start "Prometeo API :8000" cmd /k "cd /d "%ROOT%" && pnpm dev:api"

echo Starting Next.js frontend in a new window...
start "Prometeo Web :3000" cmd /k "cd /d "%ROOT%" && pnpm dev:web"

echo.
echo Both services are launching. Close those windows to stop them.
echo Docker DB keeps running; stop with:  docker compose stop db
echo.
exit /b 0
