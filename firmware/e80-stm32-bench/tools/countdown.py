#!/usr/bin/env python3
"""Countdown to T0 with terminal bell beeps.

Usage: python3 countdown.py <t0_epoch>

Prints a countdown starting at T-10s, beeping at each second.
Prints 'GO!' when T0 arrives.
"""
import sys
import time

def main():
    if len(sys.argv) < 2:
        return
    t0 = int(sys.argv[1])
    now = time.time()
    remaining = t0 - now

    if remaining <= 0:
        print("GO!")
        return

    # Print initial status
    print(f"Countdown: {int(remaining)}s remaining")

    # Beep at T-10, T-5, T-4, T-3, T-2, T-1
    beep_points = [10, 5, 4, 3, 2, 1]
    for bp in beep_points:
        wait = t0 - bp - time.time()
        if wait > 0:
            time.sleep(wait)
        if t0 - time.time() <= bp:
            sys.stdout.write(f"T-{bp} ")
            sys.stdout.flush()
            # Terminal bell
            sys.stdout.write("\a")
            sys.stdout.flush()

    # Wait for T0
    wait = t0 - time.time()
    if wait > 0:
        time.sleep(wait)
    print("GO!")

if __name__ == "__main__":
    main()