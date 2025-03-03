#!/bin/bash
# Sabrina AI Launcher Script
# This script manages starting and stopping Sabrina AI components

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PATH="${PROJECT_DIR}/venv"
LOGS_DIR="${PROJECT_DIR}/logs"
PID_DIR="${PROJECT_DIR}/.pid"
CONFIG_PATH="${PROJECT_DIR}/config/settings.yaml"

# Create required directories
mkdir -p "${LOGS_DIR}"
mkdir -p "${PID_DIR}"

# Check for Python virtual environment
check_venv() {
    if [ ! -d "${VENV_PATH}" ]; then
        echo -e "${RED}Error: Virtual environment not found at ${VENV_PATH}${NC}"
        echo -e "Please run the installation script first, or create a virtual environment with:"
        echo -e "${CYAN}python -m venv ${VENV_PATH}${NC}"
        exit 1
    fi
}

# Activate virtual environment
activate_venv() {
    if [ -f "${VENV_PATH}/bin/activate" ]; then
        source "${VENV_PATH}/bin/activate"
    elif [ -f "${VENV_PATH}/Scripts/activate" ]; then
        source "${VENV_PATH}/Scripts/activate"
    else
        echo -e "${RED}Error: Cannot find virtual environment activation script${NC}"
        exit 1
    fi
}

# Check if a service is running
is_running() {
    local service_name="$1"
    local pid_file="${PID_DIR}/${service_name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null; then
            return 0 # Running
        else
            # Stale PID file
            rm -f "$pid_file"
        fi
    fi
    return 1 # Not running
}

# Start a service
start_service() {
    local service_name="$1"
    local command="$2"
    local log_file="${LOGS_DIR}/${service_name}.log"
    local pid_file="${PID_DIR}/${service_name}.pid"

    # Check if already running
    if is_running "$service_name"; then
        echo -e "${YELLOW}Service $service_name is already running${NC}"
        return
    fi

    echo -e "${GREEN}Starting $service_name...${NC}"

    # Start service in background
    nohup $command > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"

    # Wait briefly and check if process is still running
    sleep 2
    if ps -p $pid > /dev/null; then
        echo -e "${GREEN}Service $service_name started with PID $pid${NC}"
    else
        echo -e "${RED}Failed to start $service_name. Check logs at $log_file${NC}"
        rm -f "$pid_file"
    fi
}

# Stop a service
stop_service() {
    local service_name="$1"
    local pid_file="${PID_DIR}/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        echo -e "${YELLOW}Service $service_name is not running${NC}"
        return
    fi

    local pid=$(cat "$pid_file")
    echo -e "${GREEN}Stopping $service_name (PID $pid)...${NC}"

    kill $pid 2>/dev/null

    # Wait for process to exit
    for i in {1..5}; do
        if ! ps -p $pid > /dev/null; then
            break
        fi
        sleep 1
    done

    # Force kill if still running
    if ps -p $pid > /dev/null; then
        echo -e "${YELLOW}Forcing kill of $service_name (PID $pid)...${NC}"
        kill -9 $pid 2>/dev/null
    fi

    rm -f "$pid_file"
    echo -e "${GREEN}Service $service_name stopped${NC}"
}

# Show service status
status_service() {
    local service_name="$1"

    if is_running "$service_name"; then
        local pid=$(cat "${PID_DIR}/${service_name}.pid")
        echo -e "${GREEN}Service $service_name is running (PID $pid)${NC}"
    else
        echo -e "${RED}Service $service_name is not running${NC}"
    fi
}

# Show logs for a service
tail_logs() {
    local service_name="$1"
    local log_file="${LOGS_DIR}/${service_name}.log"

    if [ ! -f "$log_file" ]; then
        echo -e "${RED}No log file found for $service_name${NC}"
        return
    fi

    echo -e "${CYAN}Showing logs for $service_name (Ctrl+C to exit)${NC}"
    tail -f "$log_file"
}

# Start the voice service
start_voice() {
    check_venv
    activate_venv

    start_service "voice" "python ${PROJECT_DIR}/services/voice/voice_api.py"
}

# Start the presence service
start_presence() {
    check_venv
    activate_venv

    start_service "presence" "python ${PROJECT_DIR}/services/presence/run.py"
}

# Start the Sabrina core
start_core() {
    check_venv
    activate_venv

    start_service "core" "python ${PROJECT_DIR}/scripts/start_sabrina.py --config ${CONFIG_PATH}"
}

# Start all services
start_all() {
    start_voice
    sleep 2 # Wait for voice service to initialize
    start_presence
    sleep 1
    start_core

    echo -e "\n${GREEN}All Sabrina AI services started${NC}"
    echo -e "${CYAN}Use './sabrina.sh status' to check service status${NC}"
}

# Stop all services
stop_all() {
    stop_service "core"
    stop_service "presence"
    stop_service "voice"

    echo -e "\n${GREEN}All Sabrina AI services stopped${NC}"
}

# Show status of all services
status_all() {
    echo -e "${BLUE}=== Sabrina AI Services Status ===${NC}"
    status_service "core"
    status_service "presence"
    status_service "voice"
}

# Run the integration tests
run_tests() {
    check_venv
    activate_venv

    echo -e "${BLUE}Running Sabrina AI integration tests...${NC}"
    python "${PROJECT_DIR}/scripts/integration_test.py" "$@"
}

# Display help
show_help() {
    echo -e "${BLUE}Sabrina AI Launcher Script${NC}"
    echo -e "Usage: $0 COMMAND [SERVICE]"
    echo -e "\nCommands:"
    echo -e "  ${GREEN}start${NC} [service]   Start service (all, core, voice, presence)"
    echo -e "  ${GREEN}stop${NC} [service]    Stop service (all, core, voice, presence)"
    echo -e "  ${GREEN}restart${NC} [service] Restart service (all, core, voice, presence)"
    echo -e "  ${GREEN}status${NC}            Show status of all services"
    echo -e "  ${GREEN}logs${NC} [service]    Show logs for service (core, voice, presence)"
    echo -e "  ${GREEN}test${NC} [options]    Run integration tests"
    echo -e "  ${GREEN}help${NC}              Show this help message"
    echo -e "\nExamples:"
    echo -e "  $0 start all      # Start all Sabrina AI services"
    echo -e "  $0 stop voice     # Stop only the voice service"
    echo -e "  $0 logs core      # Show logs for the core service"
}

# Main command processing
case "$1" in
    start)
        case "$2" in
            all)
                start_all
                ;;
            core)
                start_core
                ;;
            voice)
                start_voice
                ;;
            presence)
                start_presence
                ;;
            *)
                echo -e "${RED}Unknown service: $2${NC}"
                show_help
                exit 1
                ;;
        esac
        ;;
    stop)
        case "$2" in
            all)
                stop_all
                ;;
            core)
                stop_service "core"
                ;;
            voice)
                stop_service "voice"
                ;;
            presence)
                stop_service "presence"
                ;;
            *)
                echo -e "${RED}Unknown service: $2${NC}"
                show_help
                exit 1
                ;;
        esac
        ;;
    restart)
        case "$2" in
            all)
                stop_all
                sleep 2
                start_all
                ;;
            core)
                stop_service "core"
                sleep 1
                start_core
                ;;
            voice)
                stop_service "voice"
                sleep 1
                start_voice
                ;;
            presence)
                stop_service "presence"
                sleep 1
                start_presence
                ;;
            *)
                echo -e "${RED}Unknown service: $2${NC}"
                show_help
                exit 1
                ;;
        esac
        ;;
    status)
        status_all
        ;;
    logs)
        case "$2" in
            core)
                tail_logs "core"
                ;;
            voice)
                tail_logs "voice"
                ;;
            presence)
                tail_logs "presence"
                ;;
            *)
                echo -e "${RED}Unknown service: $2${NC}"
                echo -e "Available services: core, voice, presence"
                exit 1
                ;;
        esac
        ;;
    test)
        shift
        run_tests "$@"
        ;;
    help)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac

exit 0
