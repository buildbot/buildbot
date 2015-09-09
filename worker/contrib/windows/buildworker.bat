@echo off
REM This file is used to run buildworker when installed into a python installation or deployed in virtualenv

setlocal
set BB_BUILDWORKER="%~dp0buildworker" 

IF EXIST "%~dp0..\python.exe" (
  REM Normal system install of python (buildworker.bat is in scripts dir, just below python.exe)
  set BB_PYTHON="%~dp0..\python"
) ELSE IF EXIST "%~dp0python.exe" (
  REM virtualenv install (buildworker.bat is in same dir as python.exe)
  set BB_PYTHON="%~dp0python"
) ELSE (
  REM Not found nearby. Use system version and hope for the best
  echo Warning! Unable to find python.exe near buildworker.bat. Using python on PATH, which might be a mismatch.
  echo.
  set BB_PYTHON=python
)

%BB_PYTHON% %BB_BUILDWORKER% %*

exit /b %ERRORLEVEL%
