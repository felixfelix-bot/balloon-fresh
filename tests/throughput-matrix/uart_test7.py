import subprocess, time, telnetlib, serial

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

# Test Board B (serial 203584200D2D0D42, UART on ttyUSB4)
proc = subprocess.Popen([
    openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 203584200D2D0D42',
    '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000',
    '-c', 'telnet_port 4445; init; halt'
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

time.sleep(3)
tn = telnetlib.Telnet('127.0.0.1', 4445, timeout=5)

# Dummy read to clear banner
tn.read_until(b'>', timeout=2)

def cmd(c):
    tn.write(c.encode() + b'\n')
    time.sleep(0.5)
    data = tn.read_until(b'>', timeout=2).decode().strip()
    for line in data.split('\n'):
        if '0x' in line and ':' in line:
            return line.strip()
    return data

sr = cmd('mdw 0x40013800')
dr = cmd('mdw 0x40013804')
print(f'Board B SR: {sr}')
print(f'Board B DR: {dr}')

tx = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.1)
tx.write(b'X')
time.sleep(0.5)

sr2 = cmd('mdw 0x40013800')
dr2 = cmd('mdw 0x40013804')
print(f'Board B SR after X: {sr2}')
print(f'Board B DR after X: {dr2}')

if '0x58' in str(dr2):
    print('Board B: CH340 TX -> STM32 PA10 WORKS!')
else:
    print('Board B: No byte received. TX line also disconnected?')

tx.close()
cmd('resp')
cmd('quit')
tn.close()
proc.terminate()
proc.wait()