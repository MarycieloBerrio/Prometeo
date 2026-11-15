@echo off
REM ==========================================================================
REM  PROMETEO - arranque diario (doble clic).
REM  Enciende PostgreSQL si hace falta, inicia la API (:8000) y la web (:3000)
REM  sin duplicarlas, y abre http://localhost:3000.
REM  Opciones: --no-browser
REM  La logica vive en tools\dev\prometeo.ps1.
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "ARGS="
if /I "%~1"=="--no-browser" set "ARGS=-NoBrowser"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\dev\prometeo.ps1" -Action start %ARGS%
set "PS_EXIT=%ERRORLEVEL%"
echo.
if not "%PS_EXIT%"=="0" (
  echo  Algo fallo ^(codigo %PS_EXIT%^). Lee los mensajes [ERROR] de arriba.
  echo  Ayuda: README.md, seccion "Como ejecutar Prometeo en Windows".
)
if not defined PROMETEO_NO_PAUSE pause
exit /b %PS_EXIT%
