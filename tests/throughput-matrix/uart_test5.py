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
    time.sleep(0.3)
    return tn.read_until(b'>', timeout=1).decode().strip()

print('DR before:', cmd('mdw 0x40013804'))
print('SR before:', cmd('mdw 0x40013800'))

tx = serial.Serial('/dev/ttyUSB3', 115200, timeout=0.1)
tx.write(b'X')
time.sleep(0.5)

print('DR after X:', cmd('mdw 0x40013804'))
print('SR after X:', cmd('mdw 0x40013800'))

tx.close()
cmd('resp')
cmd('quit')
tn.close()
proc.terminate()
proc.wait()