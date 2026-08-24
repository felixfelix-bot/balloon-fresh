import subprocess, time, telnetlib, serial

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

# Test Board A (serial 148757200D2D1425, UART on ttyUSB4)
proc = subprocess.Popen([
    openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 148757200D2D1425',
    '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000',
    '-c', 'telnet_port 4444; init; halt'
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

time.sleep(3)
tn = telnetlib.Telnet('127.0.0.1', 4444, timeout=5)
tn.read_until(b'>', timeout=2)

def cmd(c):
    tn.write(c.encode() + b'\n')
    time.sleep(0.5)
    data = tn.read_until(b'>', timeout=2).decode().strip()
    for line in data.split('\n'):
        if '0x' in line and ':' in line:
            return line.strip()
    return data

# Clear DR by reading it
dr1 = cmd('mdw 0x40013804')
sr1 = cmd('mdw 0x40013800')
print(f'Board A SR: {sr1}')
print(f'Board A DR: {dr1}')

# Send Z (0x5A) via UART
tx = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.1)
tx.write(b'Z')
time.sleep(1)

# Check if byte arrived
dr2 = cmd('mdw 0x40013804')
sr2 = cmd('mdw 0x40013800')
print(f'Board A SR after Z: {sr2}')
print(f'Board A DR after Z: {dr2}')

if '0000005a' in dr2.lower():
    print('PASS: Byte 0x5A (Z) received! CH340 TX -> STM32 RX works!')
elif dr2 != dr1:
    print(f'CHANGED: DR changed from {dr1} to {dr2}')
else:
    print('FAIL: No byte received. CH340 TX line disconnected from STM32 PA10.')

tx.close()
cmd('resp')
cmd('quit')
tn.close()
proc.terminate()
proc.wait()