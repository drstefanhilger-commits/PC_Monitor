import serial


class USBPortManager:
    """
    Minimaler COM-Port Manager:
    - Öffnet und schließt den Serial-Port deterministisch
    - Keine Threads, keine Reader/Writer
    - TabUSB erzeugt USBReader/USBWriter selbst
    """

    def __init__(self):
        self.ser = None

    # ------------------------------------------------------------
    # COM-Port öffnen
    # ------------------------------------------------------------
    def open(self, port: str, baudrate: int, model):
        """
        Öffnet den COM-Port deterministisch.
        Wird von TabUSB.connect_usb() aufgerufen.
        """
        if self.ser is not None:
            raise RuntimeError("USBPortManager: Port bereits geöffnet")

        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.1)
            model.set_connected(True)
            model.set_port(port)
            return self.ser

        except Exception as e:
            self.ser = None
            model.set_connected(False)
            raise RuntimeError(f"USBPortManager: Öffnen fehlgeschlagen: {e}")

    # ------------------------------------------------------------
    # COM-Port schließen
    # ------------------------------------------------------------
    def close(self):
        """
        Schließt den COM-Port deterministisch.
        Wird von TabUSB.disconnect_usb() aufgerufen.
        """
        try:
            if self.ser:
                self.ser.close()
        finally:
            self.ser = None
