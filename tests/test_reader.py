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
    run_reader("COM5")
