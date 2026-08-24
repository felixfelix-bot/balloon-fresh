import subprocess, time, telnetlib, serial

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

# Test: halt Board B, send ID? via UART, resume, check for response
proc = subprocess.Popen([
    openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 203584200D2D0D42',
    '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000',
    '-c', 'telnet_port 4445; init; halt'
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

time.sleep(3)
tn = telnetlib.Telnet('127.0.0.1', 4445, timeout=5)
tn.read_until(b'>', timeout=2)

def cmd(c):
    tn.write(c.encode() + b'\n')
    time.sleep(0.5)
    return tn.read_until(b'>', timeout=2).decode().strip()

# CPU is halted. Send ID? via UART while halted.
tx = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.1)
tx.read(4096)
tx.write(b'ID?\r')
time.sleep(0.5)

# Check DR — byte should be sitting there
dr = cmd('mdw 0x40013804')
print(f'DR while halted (should have ID? bytes): {dr}')

# Now RESUME the CPU — firmware polling loop should drain the bytes
cmd('resp')
tx.read(4096)
time.sleep(3)

# Check UART for response
resp = tx.read(4096)
print(f'Board B response after resume ({len(resp)}b): {resp[:300]}')

tx.close()
cmd('quit')
tn.close()
proc.terminate()
proc.wait()