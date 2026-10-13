import subprocess, time, telnetlib, serial

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

# Halt Board A, send ID? while halted, then let CPU run again
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
    return tn.read_until(b'>', timeout=2).decode().strip()

# CPU is halted. Send ID?\r via UART while halted.
tx = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.1)
tx.read(4096)
tx.write(b'ID?\r')
time.sleep(0.5)

# Verify bytes are in DR
dr = cmd('mdw 0x40013804')
sr = cmd('mdw 0x40013800')
print(f'While halted - SR: {sr} DR: {dr}')

# Let CPU run again - polling fallback should drain bytes and respond
cmd('resp')
time.sleep(3)

# Check for response
resp = tx.read(4096)
print(f'After CPU restart - response ({len(resp)}b): {resp[:500]}')

tx.close()
cmd('quit')
tn.close()
proc.terminate()
proc.wait()