import subprocess, time, telnetlib, serial

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

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

# Send ID? while halted
tx = serial.Serial('/dev/ttyUSB4', 115200, timeout=0.1)
tx.read(4096)
tx.write(b'ID?\r')
time.sleep(0.3)

dr = cmd('mdw 0x40013804')
print(f'DR while halted: {dr}')

# Let CPU run
cmd('resp')
tx.read(4096)

# Wait longer - radio init may take time
for i in range(20):
    time.sleep(1)
    r = tx.read(4096)
    if r:
        print(f'Response at {i+1}s ({len(r)}b): {r[:500]}')
        break
else:
    print('No response after 20 seconds')

tx.close()
cmd('quit')
tn.close()
proc.terminate()
proc.wait()