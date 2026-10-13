import subprocess, time, telnetlib

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

# Read NVIC ISER1 (IRQ 32-63) — USART1 is IRQ 37
print('NVIC ISER1 (0xE000E104):', cmd('mdw 0xE000E104'))
# Also read USART1 DR to clear RXNE
print('USART1 DR (0x40013804):', cmd('mdw 0x40013804'))
# Re-read SR to see if RXNE cleared
print('USART1 SR after DR read:', cmd('mdw 0x40013800'))
# Read GPIOA CRH (0x40010804) — controls PA8-PA15
print('GPIOA CRH:', cmd('mdw 0x40010804'))

cmd('resp')
cmd('quit')
tn.close()
proc.terminate()
proc.wait()