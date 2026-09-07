import serial
import time
from app.model.SDSUSBModel import SDSUSBModel, SDSMode

def run_writer(port):
    ser = serial.Serial(port, 115200, timeout=0)

    model = SDSUSBModel()
    model.set_port(port)

    print(f"[TEST] Writer gestartet auf {port}")

    # MODE = DETECT
    packet = model.build_mode_message(SDSMode.DETECT.value)
    print("[TEST] Sende MODE-Paket:", packet.hex())

    ser.write(packet)

    print("[TEST] MODE gesendet. Warte auf Antwort...")

    for _ in range(2000):
        chunk = ser.read(1024)
        if chunk:
            print("[TEST] Antwort:", chunk.hex())
            break
        time.sleep(0.001)

    ser.close()


if __name__ == "__main__":
    run_writer("COM5")   # oder deinen Port
