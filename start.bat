@echo off
chcp 65001 >nul
:: LLMProxyfier Start Script for Windows
:: Usage: start.bat [port] [host] [proxy]
:: Example: start.bat 8080 0.0.0.0 http://proxy.example.com:8080

SETLOCAL

:: Set default values
SET PORT=8080
SET HOST=0.0.0.0
SET PROXY_ARG=
SET PROXY_DISPLAY=None (using defaults)

:: Parse arguments
IF NOT "%1" == "" SET PORT=%1
IF NOT "%2" == "" SET HOST=%2
IF NOT "%3" == "" (
    SET PROXY_ARG=--proxy "%3"
    SET PROXY_DISPLAY=%3
)
ECHO ============================================
ECHO Starting LLMProxyfier...
ECHO Port: %PORT%
ECHO Host: %HOST%
ECHO Proxy: %PROXY_DISPLAY%
ECHO ============================================
ECHO.

:: Check if Python is available
WHERE python >nul 2>nul
IF %ERRORLEVEL% NEQ 0 (
    ECHO Error: Python is not installed or not in PATH
    PAUSE
    EXIT /B 1
)

:: Run the server
python main.py --port %PORT% --host %HOST% %PROXY_ARG%

ENDLOCAL