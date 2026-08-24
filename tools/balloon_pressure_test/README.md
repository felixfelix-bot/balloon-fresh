# Balloon Pressure Test Rig

BMP280 pressure/temperature logger for balloon leak rate testing.

## Hardware

- ESP32-C3 (XIAO ESP32C3 or ESP32-C3_Mini_V1)
- BMP280 breakout board
- Wiring: SDA→GPIO8, SCL→GPIO9, VCC→3.3V, GND→GND
- Pump + sealed balloon connection

## Build & Flash

```bash
source ~/esp/esp-idf/export.sh
cd tools/balloon_pressure_test/
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

## Configure

```bash
idf.py menuconfig
# → Balloon Pressure Test → Measurement interval (default: 30s)
```

## Output Format

```
[00:00:00] 1050.2 22.3
[00:00:30] 1050.1 22.3
[00:01:00] 1049.9 22.2
```

Columns: `[uptime HH:MM:SS] pressure_mbar temperature_C`

## Log Capture

```bash
# Capture serial output to file
idf.py -p /dev/ttyACM0 monitor > pressure_log.txt 2>&1
# Or use screen/pyserial
python3 -m serial.tools.miniterm /dev/ttyACM0 115200 > pressure_log.txt
```

## Analysis

```bash
python3 tools/balloon_pressure_test/plot_pressure.py pressure_log.txt --output plot.png
```

Output:
- Data points, duration, start/end values
- Raw leak rate (mbar/h)
- Temperature-compensated leak rate (mbar/h)
- Verdict: <0.5 very good, 0.5-2 OK, 2-5 marginal, >5 reject
- PNG plot (pressure + temperature vs time with trend line)

## Leak Rate Criteria

| Rate (mbar/h) | Verdict | Flight Ready? |
|----------------|--------|---------------|
| < 0.5 | Very good | Yes |
| 0.5 - 2.0 | OK | Yes (with reserve) |
| 2.0 - 5.0 | Marginal | Restricted |
| > 5.0 | Poor | No — reject |

## BMP280 Details

- Auto-detects I2C address (0x76 or 0x77)
- Oversampling: x1 pressure, x1 temperature
- Normal mode, continuous readings
- Compensation math per Bosch BST-BMP280-DS001 datasheet