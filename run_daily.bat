@echo off
setlocal

:: ============================================================
:: PF Daily Market Intelligence — 자동 실행 스크립트
:: 매일 오전 8시 Windows 작업 스케줄러에서 실행
:: ============================================================

set PROJECT_DIR=C:\Users\naqmi\pf-daily-mail
set PYTHON=C:\Users\naqmi\AppData\Local\Programs\Python\Python312\python.exe
set LOG_DIR=%PROJECT_DIR%\logs

:: 로그 폴더 생성
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: 날짜 (로케일 독립적)
for /f %%i in ('"%PYTHON%" -c "import datetime; print(datetime.date.today())"') do set TODAY=%%i

set LOGFILE=%LOG_DIR%\%TODAY%.log

echo. >> "%LOGFILE%"
echo ======================================================= >> "%LOGFILE%"
echo [%TODAY% %TIME%] PF Daily 시작 >> "%LOGFILE%"
echo ======================================================= >> "%LOGFILE%"

cd /d "%PROJECT_DIR%"
"%PYTHON%" main.py >> "%LOGFILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%TIME%] ✓ 완료 (성공) >> "%LOGFILE%"
) else (
    echo [%TIME%] ✗ 오류 발생 (exit code: %ERRORLEVEL%^) >> "%LOGFILE%"
)

endlocal
