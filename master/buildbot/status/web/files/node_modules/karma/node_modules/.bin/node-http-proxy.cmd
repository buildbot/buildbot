@IF EXIST "%~dp0\node.exe" (
  "%~dp0\node.exe"  "%~dp0\..\http-proxy\bin\node-http-proxy" %*
) ELSE (
  node  "%~dp0\..\http-proxy\bin\node-http-proxy" %*
)