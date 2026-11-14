@echo off
cd /d "%~dp0"
echo === 1/2: Bygger DefineOptimization.exe ===
set "PY=python"
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
py -3.13 --version >nul 2>&1 && set "PY=py -3.13"
echo Bruker: %PY%
%PY% --version
if not exist DefineOptimization.pyw (
  echo Fant ikke DefineOptimization.pyw i denne mappen.
  goto fail
)
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%PY% -m pip install --upgrade pyinstaller
%PY% -m PyInstaller --clean --onefile --noconsole --name DefineOptimization DefineOptimization.pyw
if errorlevel 1 goto fail
if not exist dist\DefineOptimization.exe (
  echo Bygget ga ingen DefineOptimization.exe.
  goto fail
)

echo === 2/2: Bygger installer ===
set ISCC=
for %%V in (7 6) do (
  if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup %%V\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup %%V\ISCC.exe"
  if not defined ISCC if exist "%ProgramFiles%\Inno Setup %%V\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup %%V\ISCC.exe"
  if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup %%V\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup %%V\ISCC.exe"
)
if not defined ISCC for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC (
  echo.
  echo Fant ikke Inno Setup (ISCC.exe). Last ned gratis fra https://jrsoftware.org/isdl.php
  echo og kjor denne filen pa nytt.
  goto fail
)
"%ISCC%" installer.iss
if errorlevel 1 goto fail

echo.
echo Ferdig!
echo   Til GitHub-release:  dist\DefineOptimization.exe
echo   Til nye brukere:     installer_output\DefineOptimization_Setup.exe
pause
exit /b 0
:fail
echo.
echo Noe gikk galt, se meldingene over.
pause
exit /b 1
