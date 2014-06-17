@IF EXIST "%~dp0\node.exe" (
  "%~dp0\node.exe"  "%~dp0\..\karma-cli\bin\karma" %*
) ELSE (
  node  "%~dp0\..\karma-cli\bin\karma" %*
)