@echo off
setlocal
set "LAUNCH=%USERPROFILE%\.xian-skills\xian-launcher.txt"
set "XIANEXE="
if exist "%LAUNCH%" set /p XIANEXE=<"%LAUNCH%"
if defined XIANEXE if exist "%XIANEXE%" (
  "%XIANEXE%" %*
  exit /b %ERRORLEVEL%
)
where xian >nul 2>nul
if not errorlevel 1 (
  xian %*
  exit /b %ERRORLEVEL%
)
python -m xian_skills %*
exit /b %ERRORLEVEL%
