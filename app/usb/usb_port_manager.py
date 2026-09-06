# usb_port_manager.py

import threading
import serial
import logging

from .usb_reader import USBReader

logging.basicConfig(level=logging.INFO)


class USBPortManager:
    """
    Singleton-Owner für den COM-Port.
    Garantiert: nur EIN Thread öffnet/benutzt den Port.
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.ser = None
        self.reader_thread = None
        self.running = False
        self.thread_lock = threading.Lock()

    # ------------------------------------------------------------
    # OPEN PORT
    # ------------------------------------------------------------
    def open(self, port, baud, model):
        with self.thread_lock:

            # Falls bereits offen → zuerst schließen
            if self.reader_thread:
                self.reader_thread.stop()
                self.reader_thread.join()
                self.reader_thread = None

            # COM-Port öffnen
            self.ser = serial.Serial(port, baud, timeout=0.1)

            # Reader starten
            self.running = True
            self.reader_thread = USBReader(self.ser, model)
            self.reader_thread.start()

    # ------------------------------------------------------------
    # CLOSE PORT
    # ------------------------------------------------------------
    def close(self):
        with self.thread_lock:
            self.running = False

            # Reader stoppen
            if self.reader_thread:
                self.reader_thread.stop()
                self.reader_thread.join()
                self.reader_thread = None

            # Port wird vom Reader geschlossen
            self.ser = None

    # ------------------------------------------------------------
    # SEND MODE MESSAGE
    # ------------------------------------------------------------
    def send_mode(self, mode_id):
        if not self.ser:
            return

        packet = self.reader_thread.model.build_mode_message(mode_id)

        try:
            self.ser.write(packet)
        except Exception as e:
            logging.error(f"send_mode failed: {e}")
