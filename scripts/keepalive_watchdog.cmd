@echo off
REM Full 评测保活看门狗：若 keepalive.py 未运行则拉起。
REM Railway Free 强制休眠，若容器冷启动需 19 分钟而官方重试预算仅约 10 分钟，
REM 因此必须保证 /health 持续被访问。
setlocal
set PY=python
set SCRIPT=C:\Users\OTTO\Desktop\比赛\scripts\keepalive.py
set LOG=%TEMP%\aml-keepalive-watchdog.log
set STOP=%TEMP%\aml-keepalive-watchdog.stop

if exist "%STOP%" goto :eof

tasklist /FI "IMAGENAME eq python.exe" /FO CSV 2>nul | findstr /I "python.exe" >nul
REM 用 WMIC 精确判断 keepalive.py 是否在跑
for /f "delims=" %%A in ('powershell -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'keepalive.py' } | Measure-Object).Count"') do set RUNNING=%%A

if "%RUNNING%"=="0" (
    echo %DATE% %TIME% starting keepalive>> "%LOG%"
    start "" /B "%PY%" "%SCRIPT%" --hours 24 --log "%TEMP%\aml-keepalive-auto.log" --stop-file "%TEMP%\aml-keepalive-auto.stop"
) else (
    echo %DATE% %TIME% keepalive alive (%RUNNING%)>> "%LOG%"
)
endlocal
