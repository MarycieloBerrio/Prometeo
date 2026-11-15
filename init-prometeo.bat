@echo off
REM ==========================================================================
REM  PROMETEO - configuracion inicial (primera vez, o despues de un git pull
REM  que cambie dependencias). Doble clic, o desde una terminal:
REM    init-prometeo.bat                  configura y luego inicia Prometeo
REM    init-prometeo.bat --setup-only     configura sin iniciar API/web
REM    init-prometeo.bat --with-knowledge instala tambien paquetes de Knowledge Base
REM    init-prometeo.bat --build-kb       ademas construye la Knowledge Base si esta vacia
REM    init-prometeo.bat --rebuild-kb     actualiza la Knowledge Base aunque ya tenga datos
REM  Nunca sobrescribe .env, nunca borra contenedores, volumenes ni documentos.
REM  La logica vive en tools\dev\prometeo.ps1.
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "ACTION=setup"
set "ARGS="
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--setup-only" set "ARGS=%ARGS% -SetupOnly"
if /I "%~1"=="--with-knowledge" set "ARGS=%ARGS% -WithKnowledge"
if /I "%~1"=="--build-kb" set "ARGS=%ARGS% -BuildKb -Scope all"
if /I "%~1"=="--rebuild-kb" set "ACTION=kb"
if /I "%~1"=="--rebuild-kb" set "ARGS=%ARGS% -RebuildKb -Scope all"
if /I "%~1"=="--no-browser" set "ARGS=%ARGS% -NoBrowser"
if /I "%~1"=="-h" goto usage
if /I "%~1"=="--help" goto usage
shift
goto parse_args
:usage
findstr /B "REM" "%~f0"
exit /b 0
:args_done
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\dev\prometeo.ps1" -Action %ACTION% %ARGS%
set "PS_EXIT=%ERRORLEVEL%"
echo.
if not "%PS_EXIT%"=="0" (
  echo  Algo fallo ^(codigo %PS_EXIT%^). Lee los mensajes [ERROR] de arriba.
  echo  Ayuda: README.md, seccion "Como ejecutar Prometeo en Windows".
)
if not defined PROMETEO_NO_PAUSE pause
exit /b %PS_EXIT%
