import subprocess, time, telnetlib, serial

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

proc = subprocess.Popen([
    openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 148757200D2D1425',
    '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000',
    '-c', 'telnet_port 4444; init; halt'
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

time.sleep(3)
tn = telnetlib.Telnet('127.0.0.1', 4444, timeout=5)

def cmd(c):
    tn.write(c.encode() + b'\n')
    time.sleep(0.5)
    data = tn.read_until(b'>', timeout=2).decode().strip()
    for line in data.split('\n'):
        if '0x' in line and ':' in line:
            return line.strip()
    return data

sr_before = cmd('mdw 0x40013800')
dr_before = cmd('mdw 0x40013804')
print(f'SR before: {sr_before}')
print(f'DR before: {dr_before}')

tx = serial.Serial('/dev/ttyUSB3', 115200, timeout=0.1)
tx.write(b'X')
time.sleep(0.5)

sr_after = cmd('mdw 0x40013800')
dr_after = cmd('mdw 0x40013804')
print(f'SR after X: {sr_after}')
print(f'DR after X: {dr_after}')

# 0x58 = 'X'. If DR shows 0x58, physical TX path works.
if '0x58' in dr_after:
    print('RESULT: CH340 TX -> STM32 PA10 WORKS! Byte received.')
elif dr_after == dr_before:
    print('RESULT: No change in DR. CH340 TX line may be disconnected.')
else:
    print(f'RESULT: DR changed to {dr_after}. Checking if it is 0x58 (X)...')

tx.close()
cmd('resp')
cmd('quit')
tn.close()
proc.terminate()
proc.wait()