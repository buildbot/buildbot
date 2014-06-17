@IF EXIST "%~dp0\node.exe" (
  "%~dp0\node.exe"  "%~dp0\..\ncp\bin\ncp" %*
) ELSE (
  node  "%~dp0\..\ncp\bin\ncp" %*
)