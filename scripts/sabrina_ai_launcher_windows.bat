@echo off
REM Sabrina AI Launcher Script for Windows
REM This script manages starting and stopping Sabrina AI components

setlocal enabledelayedexpansion

REM Configuration
set PROJECT_DIR=%~dp0
set VENV_PATH=%PROJECT_DIR%venv
set LOGS_DIR=%PROJECT_DIR%logs
set PID_DIR=%PROJECT_DIR%.pid
set CONFIG_PATH=%PROJECT_DIR%config\settings.yaml

REM Create required directories
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

REM Set title
title Sabrina AI Launcher

REM Check for Python virtual environment
:check_venv
if not exist "%VENV_PATH%" (
    echo Error: Virtual environment not found at %VENV_PATH%
    echo Please run the installation script first, or create a virtual environment with:
    echo python -m venv %VENV_PATH%
    exit /b 1
)

REM Check if a service is running
:is_running
set SERVICE_NAME=%~1
set PID_FILE=%PID_DIR%\%SERVICE_NAME%.pid

if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"

    REM Check if process with this PID exists
    tasklist /FI "PID eq !PID!" 2>NUL | find /i "!PID!" >NUL
    if !errorlevel! equ 0 (
        REM Process is running
        exit /b 0
    ) else (
        REM Stale PID file
        del "%PID_FILE%" 2>NUL
    )
)
exit /b 1

REM Start a service
:start_service
set SERVICE_NAME=%~1
set COMMAND=%~2
set LOG_FILE=%LOGS_DIR%\%SERVICE_NAME%.log
set PID_FILE=%PID_DIR%\%SERVICE_NAME%.pid

REM Check if already running
call :is_running %SERVICE_NAME%
if !errorlevel! equ 0 (
    echo Service %SERVICE_NAME% is already running.
    exit /b 0
)

echo Starting %SERVICE_NAME%...

REM Start service in background using start command
start /B "Sabrina %SERVICE_NAME%" cmd /c "call %VENV_PATH%\Scripts\activate.bat && %COMMAND% > "%LOG_FILE%" 2>&1"

REM Get PID of last started process (Windows way)
for /f "tokens=2" %%a in ('tasklist /v /fo csv /nh /fi "WINDOWTITLE eq Sabrina %SERVICE_NAME%"') do (
    set PID=%%~a
    echo !PID!>"%PID_FILE%"
    echo Service %SERVICE_NAME% started with PID !PID!
    exit /b 0
)

echo Failed to start %SERVICE_NAME%. Check logs at %LOG_FILE%
exit /b 1

REM Stop a service
:stop_service
set SERVICE_NAME=%~1
set PID_FILE=%PID_DIR%\%SERVICE_NAME%.pid

if not exist "%PID_FILE%" (
    echo Service %SERVICE_NAME% is not running.
    exit /b 0
)

set /p PID=<"%PID_FILE%"
echo Stopping %SERVICE_NAME% (PID !PID!)...

REM Try to kill process
taskkill /PID !PID! /F >NUL 2>&1

REM Clean up PID file
del "%PID_FILE%" 2>NUL
echo Service %SERVICE_NAME% stopped.
exit /b 0

REM Show service status
:status_service
set SERVICE_NAME=%~1

call :is_running %SERVICE_NAME%
if !errorlevel! equ 0 (
    set /p PID=<"%PID_DIR%\%SERVICE_NAME%.pid"
    echo Service %SERVICE_NAME% is running (PID !PID!)
) else (
    echo Service %SERVICE_NAME% is not running.
)
exit /b 0

REM Show logs for a service
:tail_logs
set SERVICE_NAME=%~1
set LOG_FILE=%LOGS_DIR%\%SERVICE_NAME%.log

if not exist "%LOG_FILE%" (
    echo No log file found for %SERVICE_NAME%
    exit /b 1
)

echo Showing logs for %SERVICE_NAME% (Close window to exit)
start "Sabrina Logs - %SERVICE_NAME%" powershell -Command "Get-Content -Path '%LOG_FILE%' -Wait -Tail 50"
exit /b 0

REM Start the voice service
:start_voice
call :start_service "voice" "python %PROJECT_DIR%services\voice\voice_api.py"
exit /b !errorlevel!

REM Start the presence service
:start_presence
call :start_service "presence" "python %PROJECT_DIR%services\presence\run.py"
exit /b !errorlevel!

REM Start the Sabrina core
:start_core
call :start_service "core" "python %PROJECT_DIR%scripts\start_sabrina.py --config %CONFIG_PATH%"
exit /b !errorlevel!

REM Start all services
:start_all
call :start_voice
timeout /t 2 > NUL
call :start_presence
timeout /t 1 > NUL
call :start_core

echo.
echo All Sabrina AI services started
echo Use 'sabrina.bat status' to check service status
exit /b 0

REM Stop all services
:stop_all
call :stop_service "core"
call :stop_service "presence"
call :stop_service "voice"

echo.
echo All Sabrina AI services stopped
exit /b 0

REM Show status of all services
:status_all
echo === Sabrina AI Services Status ===
call :status_service "core"
call :status_service "presence"
call :status_service "voice"
exit /b 0

REM Run the integration tests
:run_tests
echo Running Sabrina AI integration tests...
call "%VENV_PATH%\Scripts\activate.bat"
python "%PROJECT_DIR%scripts\integration_test.py" %*
exit /b !errorlevel!

REM Display help
:show_help
echo Sabrina AI Launcher Script for Windows
echo Usage: %0 COMMAND [SERVICE]
echo.
echo Commands:
echo   start [service]   Start service (all, core, voice, presence)
echo   stop [service]    Stop service (all, core, voice, presence)
echo   restart [service] Restart service (all, core, voice, presence)
echo   status            Show status of all services
echo   logs [service]    Show logs for service (core, voice, presence)
echo   test [options]    Run integration tests
echo   help              Show this help message
echo.
echo Examples:
echo   %0 start all      # Start all Sabrina AI services
echo   %0 stop voice     # Stop only the voice service
echo   %0 logs core      # Show logs for the core service
exit /b 0

REM Main command processing
if "%1" == "" goto show_help

if "%1" == "start" (
    if "%2" == "all" goto start_all
    if "%2" == "core" goto start_core
    if "%2" == "voice" goto start_voice
    if "%2" == "presence" goto start_presence
    echo Unknown service: %2
    goto show_help
) else if "%1" == "stop" (
    if "%2" == "all" goto stop_all
    if "%2" == "core" call :stop_service "core" & exit /b
    if "%2" == "voice" call :stop_service "voice" & exit /b
    if "%2" == "presence" call :stop_service "presence" & exit /b
    echo Unknown service: %2
    goto show_help
) else if "%1" == "restart" (
    if "%2" == "all" (
        call :stop_all
        timeout /t 2 > NUL
        goto start_all
    )
    if "%2" == "core" (
        call :stop_service "core"
        timeout /t 1 > NUL
        goto start_core
    )
    if "%2" == "voice" (
        call :stop_service "voice"
        timeout /t 1 > NUL
        goto start_voice
    )
    if "%2" == "presence" (
        call :stop_service "presence"
        timeout /t 1 > NUL
        goto start_presence
    )
    echo Unknown service: %2
    goto show_help
) else if "%1" == "status" (
    goto status_all
) else if "%1" == "logs" (
    if "%2" == "core" call :tail_logs "core" & exit /b
    if "%2" == "voice" call :tail_logs "voice" & exit /b
    if "%2" == "presence" call :tail_logs "presence" & exit /b
    echo Unknown service: %2
    echo Available services: core, voice, presence
    exit /b 1
) else if "%1" == "test" (
    shift
    goto run_tests
) else if "%1" == "help" (
    goto show_help
) else (
    echo Unknown command: %1
    goto show_help
)

endlocal
