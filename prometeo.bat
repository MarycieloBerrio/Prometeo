@echo off
REM ==========================================================================
REM  PROMETEO - menu local (doble clic):
REM    1 Iniciar  2 Configuracion inicial  3 Knowledge Base
REM    4 Verificar servicios  5 Detener API/web  6 Salir
REM  La logica vive en tools\dev\prometeo.ps1.
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\dev\prometeo.ps1" -Action menu
set "PS_EXIT=%ERRORLEVEL%"
echo.
if not "%PS_EXIT%"=="0" (
  echo  Algo fallo ^(codigo %PS_EXIT%^). Lee los mensajes [ERROR] de arriba.
  echo  Ayuda: README.md, seccion "Como ejecutar Prometeo en Windows".
)
if not defined PROMETEO_NO_PAUSE pause
exit /b %PS_EXIT%
