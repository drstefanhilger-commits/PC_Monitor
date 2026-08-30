import math
import serial
import struct
import time
import matplotlib.pyplot as plt
from collections import deque
import zlib
import tkinter as tk
from tkinter import ttk

# ------------------------------------------------------------
# Konfiguration
# ------------------------------------------------------------
PORT = "COM5"
BAUD = 115200

# SDS Detection Frame (24 Bytes)
FRAME_SIZE_DET = 24
MAGIC = 0xDEADBEEF

# UnixTime Sync Frame (12 Bytes)
FRAME_SIZE_SYNC = 12

# ------------------------------------------------------------
# Tkinter GUI Setup
# ------------------------------------------------------------
root = tk.Tk()
root.title("SRP Monitor Control")

# Button zum Senden der UnixTime Sync Message
def on_button_click():
    send_time_sync(ser)

btn = ttk.Button(root, text="Send UnixTime Sync", command=on_button_click)
btn.pack(padx=10, pady=10)

root.update()   # GUI starten

# ------------------------------------------------------------
# Plot Setup
# ------------------------------------------------------------
plt.ion()

fig = plt.figure(figsize=(7, 12))
gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 1.4])

ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

az_history = deque(maxlen=200)
dist_history = deque(maxlen=200)

line_az, = ax1.plot([], [], 'r-')
line_dist, = ax2.plot([], [], 'b-')

ax1.set_title("Azimuth (degrees)")
ax2.set_title("Distance (meters)")
ax3.set_title("Vector Plot (Cartesian)")

ax1.set_ylim(0, 360)
ax2.set_ylim(40, 110)

# --- ax3 quadratisch ---
ax3.set_xlim(-100, 100)
ax3.set_ylim(-100, 100)
ax3.set_aspect("equal", adjustable="box")
ax3.grid(True)

point, = ax3.plot([], [], 'go', markersize=8)
vector, = ax3.plot([], [], 'g-', linewidth=2)

# ------------------------------------------------------------
# Serial öffnen
# ------------------------------------------------------------
print(f"Opening {PORT} ...")
ser = serial.Serial(PORT, BAUD, timeout=1)

print("Listening for SDS + UnixTime Sync Messages...\n")

# ------------------------------------------------------------
# UnixTime Sync Sender
# ------------------------------------------------------------
def send_time_sync(ser):
    unix_time = int(time.time())

    msg_id = 1
    len0, len1, len2 = 0, 0, 12  # 12 bytes total
    payload = struct.pack("<I", unix_time)

    crc = zlib.crc32(payload) & 0xFFFFFFFF

    header = struct.pack("<BBBBI", msg_id, len0, len1, len2, unix_time)
    packet = header + struct.pack("<I", crc)

    ser.write(packet)
    print(f"[SEND] UnixTime Sync sent: {unix_time}")

# ------------------------------------------------------------
# Hauptloop
# ------------------------------------------------------------
last_sync = time.time()

while True:

    # Tkinter GUI responsive halten
    root.update()

    # Wir lesen immer 1 Byte und entscheiden dann, was kommt
    first = ser.read(1)
    if len(first) == 0:
        continue

    b0 = first[0]

    # ------------------------------------------------------------
    # Fall A: UnixTime Sync Message (ID = 1)
    # ------------------------------------------------------------
    if b0 == 1:
        rest = ser.read(FRAME_SIZE_SYNC - 1)
        if len(rest) != FRAME_SIZE_SYNC - 1:
            continue

        msg_id, len0, len1, len2, unix_time, crc = struct.unpack("<BBBBII", first + rest)

        print(f"[SYNC] UnixTime={unix_time}  CRC=0x{crc:08X}")
        continue

    # ------------------------------------------------------------
    # Fall B: SDS Detection Frame (MAGIC = 0xDEADBEEF)
    # ------------------------------------------------------------
    else:
        magic_bytes = first + ser.read(3)
        if len(magic_bytes) != 4:
            continue

        magic = struct.unpack("<I", magic_bytes)[0]

        if magic != MAGIC:
            print(f"[WARN] Unknown frame start: 0x{magic:08X}")
            continue

        rest = ser.read(FRAME_SIZE_DET - 4)
        if len(rest) != FRAME_SIZE_DET - 4:
            continue

        ts, mic, azi, ele, conf = struct.unpack("<IIfff", rest)

        print(f"[SDS] TS={ts:10d}  Mic={mic}  Az={azi:7.2f}°  Dist={ele:7.2f}m  Conf={conf:5.2f}")

        # --------------------------------------------------------
        # Plot aktualisieren
        # --------------------------------------------------------
        az_history.append(azi)
        dist_history.append(ele)

        line_az.set_xdata(range(len(az_history)))
        line_az.set_ydata(az_history)

        line_dist.set_xdata(range(len(dist_history)))
        line_dist.set_ydata(dist_history)

        ax1.relim()
        ax1.autoscale_view()

        ax2.relim()
        ax2.autoscale_view()

        # Polar → Kartesisch
        azi_rad = math.radians(azi)
        x = ele * math.cos(azi_rad)
        y = ele * math.sin(azi_rad)

        point.set_xdata([x])
        point.set_ydata([y])

        vector.set_xdata([0, x])
        vector.set_ydata([0, y])

        plt.pause(0.01)

    # ------------------------------------------------------------
    # Periodisches Senden der Unix-Time
    # ------------------------------------------------------------
    if time.time() - last_sync > 1.0:
        send_time_sync(ser)
        last_sync = time.time()
