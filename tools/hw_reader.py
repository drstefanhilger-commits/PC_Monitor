"""Hardware-Hilfsskript: Rohbytes eines echten Ports ausgeben.
Aufruf: python -m tools.hw_reader [PORT]   (Standard COM5)
"""
import sys

import serial
import time

def run_reader(port):
    ser = serial.Serial(port, 115200, timeout=0)

    print(f"[TEST] Reader gestartet auf {port}")

    while True:
        chunk = ser.read(1024)
        if chunk:
            print("[TEST] RAW:", chunk.hex())
        time.sleep(0.001)


if __name__ == "__main__":
    run_reader(sys.argv[1] if len(sys.argv) > 1 else "COM5")
