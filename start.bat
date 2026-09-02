@echo off
REM GUS-DEDEKTIV. Double-click this file to run the whole platform.
REM Passes any arguments through, so this works too:
REM   start.bat -Reseed
REM   start.bat -NoBrowser -ApiPort 8010
title GUS-DEDEKTIV
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
if errorlevel 1 pause
