import subprocess, time, telnetlib

openocd = '/home/c03rad0r/.espressif/tools/openocd-esp32/v0.12.0-esp32-20241016/openocd-esp32/bin/openocd'

proc = subprocess.Popen([
    openocd, '-f', 'interface/cmsis-dap.cfg', '-c', 'adapter serial 148757200D2D1425',
    '-f', 'target/stm32f1x.cfg', '-c', 'adapter speed 1000',
    '-c', 'init; halt; telnet_port 4444'
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

time.sleep(3)

try:
    tn = telnetlib.Telnet('127.0.0.1', 4444, timeout=5)
    def cmd(c):
        tn.write(c.encode() + b'\n')
        time.sleep(0.3)
        return tn.read_until(b'>', timeout=1).decode().strip()
    print('CR1:', cmd('mdw 0x4001380C'))
    print('SR:',  cmd('mdw 0x40013800'))
    print('NVIC:',cmd('mdw 0xE000E100'))
    print('CRH:', cmd('mdw 0x40010804'))
    cmd('resp')
    cmd('quit')
    tn.close()
except Exception as e:
    print(f'Telnet failed: {e}')
    # Read openocd output for debugging
    time.sleep(1)
    proc.terminate()
    out = proc.stdout.read()
    print(out.decode()[-500:])
    sys.exit(1)

proc.terminate()
proc.wait()