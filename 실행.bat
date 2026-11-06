@echo off
title findJob 서버
cd /d "%~dp0"

rem 이미 켜져 있으면 브라우저만 연다
netstat -ano | findstr ":8501 " | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo findJob 서버가 이미 켜져 있습니다. 브라우저를 엽니다.
    start "" http://localhost:8501
    timeout /t 3 >nul
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo [오류] 파이썬을 찾을 수 없습니다. 파이썬을 설치한 뒤 다시 실행하세요.
    pause
    exit /b 1
)

echo findJob 서버를 켭니다. 잠시 뒤 브라우저가 열립니다.
echo 이 창을 닫거나 Ctrl+C 를 누르면 서버가 꺼집니다.
echo.
python -m streamlit run app.py --server.port 8501

echo.
echo 서버가 종료되었습니다.
pause
