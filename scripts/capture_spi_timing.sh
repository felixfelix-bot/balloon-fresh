#!/bin/bash
# Logic analyzer capture script for LR2021 SPI timing analysis
# 
# Captures SPI bus traffic during FLRC TX burst
# Connect logic analyzer to:
#   Channel 0: GP2 (SCK)
#   Channel 1: GP3 (MOSI)
#   Channel 2: GP4 (MISO)  
#   Channel 3: GP5 (CS/NSS)
#   Channel 4: GP6 (BUSY)
#   Channel 5: GP7 (IRQ/DIO9)
#   GND: any GND
#
# Usage: ./capture_spi_timing.sh [duration_seconds] [sample_rate_hz]

set -e

DURATION=${1:-2}
RATE=${2:-24000000}  # 24 MHz sample rate (2x SPI clock for oversampling)
OUTPUT_DIR="/tmp/spi_captures"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$OUTPUT_DIR/spi_capture_${TIMESTAMP}"

echo "=== SPI Timing Capture ==="
echo "Duration: ${DURATION}s"
echo "Sample rate: ${RATE} Hz ($(echo "scale=1; $RATE/1000000" | bc) MHz)"
echo "Output: $OUTPUT_FILE"

# Detect logic analyzer
echo ""
echo "Detecting logic analyzer..."
LA_DRIVER=$(sigrok-cli --list-supported 2>/dev/null | grep -iE 'fx2lafw|saleae|usb|zeroplus' | head -1 | awk '{print $1}')
echo "Candidate driver: $LA_DRIVER"

# Try common drivers for cheap USB logic analyzers
for drv in fx2lafw saleae-logic16 usb-ix-32 usb-fx2; do
    if sigrok-cli --driver=$drv --show 2>/dev/null | grep -q 'sr'; then
        echo "Found logic analyzer: $drv"
        LA_DRIVER=$drv
        break
    fi
done

# Capture
echo ""
echo "Starting capture... Trigger TX burst NOW (send RUN to TX board)"
echo ""

# Common 8-channel USB logic analyzer (fx2lafw / Saleae clone)
# Channels: D0-D7 mapped to our 6 signals
sigrok-cli \
    --driver=fx2lafw \
    --channels=D0=SCK,D1=MOSI,D2=MISO,D3=CS,D4=BUSY,D5=IRQ \
    --config samplerate=${RATE} \
    --continuous \
    --output-file=${OUTPUT_FILE}.sr \
    --time ${DURATION}s \
    2>&1 || {
        echo "fx2lafw failed, trying other drivers..."
        for drv in saleae-logic kingst-la2016 uni-t-ut372c; do
            sigrok-cli \
                --driver=$drv \
                --config samplerate=${RATE} \
                --output-file=${OUTPUT_FILE}.sr \
                --time ${DURATION}s \
                2>&1 && break
        done
    }

echo ""
echo "Capture complete: ${OUTPUT_FILE}.sr"

# Export to CSV for analysis
echo "Exporting to CSV..."
sigrok-cli \
    --input-file ${OUTPUT_FILE}.sr \
    --output-file ${OUTPUT_FILE}.csv \
    --output-format csv 2>/dev/null && echo "CSV: ${OUTPUT_FILE}.csv" || echo "CSV export failed (non-critical)"

# Quick analysis
echo ""
echo "=== Quick SPI Analysis ==="
echo "Analyzing CS assertion timing..."

if [ -f "${OUTPUT_FILE}.csv" ]; then
    # Count CS falling edges (transaction starts)
    CS_STARTS=$(awk -F',' 'NR>1 {if($4==0 && prev4==1) count++} {prev4=$4} END{print count+0}' ${OUTPUT_FILE}.csv 2>/dev/null || echo "?")
    echo "CS assertions detected: $CS_STARTS"
    
    # Find SCK frequency (first few edges)
    echo "SCK analysis (first 1000 samples)..."
    head -1001 ${OUTPUT_FILE}.csv | awk -F',' 'NR>1 {
        if($1==1 && prev1==0) {
            if(rise_count < 5) {
                print "  Rising edge at sample " NR
                rise_count++
                if(last_rise > 0) {
                    period = NR - last_rise
                    freq = 24000000 / period
                    printf "  SCK period: %d samples = %.1f MHz\n", period, freq/1000000
                }
                last_rise = NR
            }
        }
        prev1=$1
    }' 2>/dev/null || echo "  (analysis incomplete)"
fi

echo ""
echo "Full analysis: open ${OUTPUT_FILE}.sr in PulseView or sigrok-cli"
echo ""
echo "To decode SPI protocol:"
echo "  sigrok-cli -i ${OUTPUT_FILE}.sr -P spi:clk=SCK:mosi=MOSI:miso=MISO:cs=CS -A spi=mosi,miso"
