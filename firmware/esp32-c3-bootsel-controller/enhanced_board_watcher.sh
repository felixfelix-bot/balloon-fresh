#!/bin/bash
# Enhanced Board Watcher with ESP32 BOOTSEL Controller Integration
# Replaces manual BOOTSEL detection with automated ESP32 control

set -euo pipefail

ESP32_PORT="${ESP32_PORT:-/dev/ttyACM1}"
RP2040_SERIAL="${RP2040_SERIAL:-/dev/ttyACM0}"
LOG_FILE="${LOG_FILE:-/tmp/board_watcher.log}"
UF2_FILE="${UF2_FILE:-$(find ~/repos/balloon-fresh/firmware/rp2040 -name '*.uf2' | head -1)}"

echo "🔧 Enhanced Board Watcher with ESP32 Controller Integration"
echo "ESP32 Port: $ESP32_PORT"
echo "RP2040 Serial: $RP2040_SERIAL"
echo "UF2 File: $UF2_FILE"
echo "Log File: $LOG_FILE"

# Function to log messages
log_message() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" | tee -a "$LOG_FILE"
}

# Function to send command to ESP32
send_esp32_command() {
    local command="$1"
    log_message "Sending command to ESP32: $command"
    
    if echo "$command" > "$ESP32_PORT" 2>/dev/null; then
        # Wait for response
        local response=$(head -1 "$ESP32_PORT" 2>/dev/null || echo "")
        log_message "ESP32 response: $response"
        
        if [[ "$response" == *"OK"* ]]; then
            return 0
        else
            log_message "❌ ESP32 command failed: $response"
            return 1
        fi
    else
        log_message "❌ Failed to send command to ESP32 on $ESP32_PORT"
        return 1
    fi
}

# Function to flash firmware using ESP32 controller
flash_firmware_esp32() {
    local firmware_type="$1"  # "RX" or "TX"
    
    log_message "🔄 Flashing $firmware_type firmware using ESP32 controller"
    
    # 1. Send appropriate flash command
    if [[ "$firmware_type" == "RX" ]]; then
        send_esp32_command "FLASH_RX" || return 1
    else
        send_esp32_command "FLASH_TX" || return 1
    fi
    
    # 2. Wait for flashing response
    log_message "⏳ Waiting for flashing to complete..."
    local timeout=30
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        local response=$(head -1 "$ESP32_PORT" 2>/dev/null || echo "")
        if [[ "$response" == *"DONE"* ]]; then
            log_message "✅ Firmware flashed successfully"
            break
        elif [[ "$response" == *"ERROR"* ]]; then
            log_message "❌ Flashing failed: $response"
            return 1
        fi
        
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    if [[ $elapsed -ge $timeout ]]; then
        log_message "❌ Flashing timeout after $timeout seconds"
        return 1
    fi
    
    # 3. Reset the RP2040
    send_esp32_command "RESET" || return 1
    
    return 0
}

# Function to monitor RP2040 health
monitor_rp2040() {
    log_message "🔄 Starting RP2040 health monitoring..."
    
    # Check if ESP32 is responsive
    if ! send_esp32_command "STATUS"; then
        log_message "❌ ESP32 controller not responding"
        return 1
    fi
    
    # Monitor heartbeats for 10 seconds
    log_message "💓 Checking RP2040 heartbeat..."
    local start_time=$(date +%s)
    local heartbeats=0
    
    while [[ $(($(date +%s) - start_time)) -lt 10 ]]; do
        local line=$(head -1 "$ESP32_PORT" 2>/dev/null || echo "")
        if [[ "$line" == *"HB rx="* ]]; then
            heartbeats=$((heartbeats + 1))
            log_message "💓 Heartbeat detected: $line"
        fi
        sleep 0.1
    done
    
    if [[ $heartbeats -gt 5 ]]; then
        log_message "✅ RP2040 healthy - $heartbeats heartbeats in 10 seconds"
        return 0
    else
        log_message "⚠️  RP2040 may be unresponsive - only $heartbeats heartbeats"
        return 1
    fi
}

# Function to check for BOOTSEL mode
check_bootsel_mode() {
    log_message "🔍 Checking for BOOTSEL mode..."
    
    # Look for RP2040 in BOOTSEL mode
    if lsblk | grep -i "rp2040" >/dev/null 2>&1; then
        log_message "✅ RP2040 detected in BOOTSEL mode"
        return 0
    else
        log_message "❌ RP2040 not in BOOTSEL mode"
        return 1
    fi
}

# Main monitoring loop
main_loop() {
    log_message "🚀 Starting enhanced board watcher loop..."
    
    while true; do
        # Check RP2040 health
        if ! monitor_rp2040; then
            log_message "🚨 RP2040 health check failed - initiating recovery"
            
            # Force recovery sequence
            log_message "🔄 Initiating recovery sequence..."
            
            # 1. Force BOOTSEL mode
            if ! send_esp32_command "BOOTSEL"; then
                log_message "❌ Failed to force BOOTSEL mode"
                sleep 30
                continue
            fi
            
            # 2. Wait for BOOTSEL mode to be ready
            sleep 2
            
            # 3. Check if we're in BOOTSEL mode
            if check_bootsel_mode; then
                # 4. Flash RX firmware
                if flash_firmware_esp32 "RX"; then
                    log_message "✅ Recovery sequence completed successfully"
                else
                    log_message "❌ Recovery sequence failed"
                fi
            else
                log_message "❌ Failed to enter BOOTSEL mode"
            fi
        fi
        
        # Normal operation - continue monitoring
        sleep 60  # Check every minute
    done
}

# Function for one-time firmware flash
flash_firmware() {
    local firmware_type="${1:-RX}"
    
    log_message "🔧 One-time firmware flash requested: $firmware_type"
    
    if [[ ! -f "$UF2_FILE" ]]; then
        log_message "❌ UF2 file not found: $UF2_FILE"
        return 1
    fi
    
    if flash_firmware_esp32 "$firmware_type"; then
        log_message "✅ Firmware flash completed successfully"
        return 0
    else
        log_message "❌ Firmware flash failed"
        return 1
    fi
}

# Parse command line arguments
case "${1:-monitor}" in
    "monitor")
        main_loop
        ;;
    "flash-rx")
        flash_firmware "RX"
        ;;
    "flash-tx")
        flash_firmware "TX"
        ;;
    "status")
        send_esp32_command "STATUS" && monitor_rp2040
        ;;
    "reset")
        send_esp32_command "RESET"
        ;;
    "bootsel")
        send_esp32_command "BOOTSEL"
        ;;
    *)
        echo "Usage: $0 {monitor|flash-rx|flash-tx|status|reset|bootsel}"
        echo ""
        echo "  monitor   - Continuous monitoring and auto-recovery"
        echo "  flash-rx  - Flash RX firmware one time"
        echo "  flash-tx  - Flash TX firmware one time"
        echo "  status    - Check system status and health"
        echo "  reset     - Reset RP2040"
        echo "  bootsel   - Force BOOTSEL mode"
        exit 1
        ;;
esac