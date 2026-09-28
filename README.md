# PC-Monitor für SDS_110

[![Tests](https://github.com/drstefanhilger-commits/PC_Monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/drstefanhilger-commits/PC_Monitor/actions/workflows/tests.yml)

GUI für die Sensoreinheit SDS_110 (STM32F746) über USB-CDC. Version: `app/__init__.py` (`__version__`, Fenstertitel und Bedienfeld).

Funktionen:
- Betriebsart und Signalquelle steuern.
- Anzeigen: Peilungen (Detect), Rohdaten (Read), Nordabgleich (Calibrate).
- Tracking-Einheit (FSL9 §8–10).
- Status und Fehler protokollieren.

Das Nachrichtenformat beschreibt SDS_110 `doc/ICD_SDS_PC_Monitor.md`.

## Start

**Windows:** `start_monitor.bat` doppelklicken. Beim ersten Start legt das Skript `.venv` an und installiert die Pakete aus `requirements.txt`. Dafür wird Python ab 3.10 von python.org gebraucht.

**Linux/macOS:** `./start_monitor.sh`

**Von Hand:**
```
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Bedienung

- **Verbindung:** Port wählen, Schalter **On** verbindet. Beim Verbinden werden gesendet:
  - Signalquelle (Real/Simulation)
  - Betriebsart
  - SRP-Referenz
  - Nordabgleich
  - Standort
  - Sync
- **Drehschalter Detect – Read – Calibrate:** wählt die Betriebsart des Boards und den angezeigten Tab.
- **Board:** Unit-ID setzen, SRP-Referenzscan aus/ein.
- **Sync:** sendet UTC und Lufttemperatur.
  - Gesendet wird beim Verbinden, jede Minute und wenn sich die Temperatur ändert.
  - Ohne Haken bei „Temp.“ gilt die Temperatur als unbekannt.
- **Standort (WGS84):** Breite, Länge und Höhe über NN der Einheit, zum Beispiel `48.137154, 11.57549, 519.5`.
  - Breite und Länge lassen sich aus Google Maps kopieren. Ohne Höhe gilt 0 m.
  - „Senden“ oder Enter sendet den Standort (Id 10) und speichert ihn; beim Verbinden wird er erneut gesendet.
  - „Board: …“ zeigt, was das Board meldet (Id 6, jede Sekunde), mit der Quelle PC oder GNSS. Orange: kein Standort oder ein anderer als der eingegebene.
  - In der Hardware-Version 2 setzt ein GPS-Modul den Standort; eine gültige GNSS-Position überschreibt der PC nicht.
  - Der CSV-Export enthält damit Breite und Länge jedes Spurpunkts.
- **Tracking:** Die Tracking-Einheit bildet aus den Reports eine Spur. Der Lageplan zeigt die letzten 10 Punkte grün; der CSV-Export enthält alle.
  - „Feedback“ sendet ŝ und die Vorhersage an das Board (Id 8).
  - „Trajektorie als CSV …“ speichert die Spuren.
- **Unten:** Status- und Fehlermeldungen.
  - Zähler RX/TX/Fehler.
  - „Leeren“ löscht Meldungen und Zähler.
  - Meldungen des Boards (Logger) erscheinen als „SDS: …“.

![Detect](docs/gui_detect.png)

### Rohdaten (Tab Read)

- Das Board sendet im Modus READ die Mikrofonsignale **vor** der Vorverarbeitung (Firmware ab 28.09.2026, ICD 5.3).
- Der Tab zeigt Pegel, Wellenform und Spektrum des letzten Hops. Außerdem zählt er fehlende Hops über die Hop-Nummer: USB Full Speed schafft nicht alle 96 Nachrichten je Hop.
- **Aufnahme …** speichert die Rohdaten als WAV (8 Kanäle, 24 Bit, 48 kHz). Fehlende oder unvollständige Hops werden als Stille geschrieben und gezählt.
- Die Datei lässt sich direkt mit SDS_110 `tools/features/sds_features` auswerten.

### Nordabgleich (Tab Calibrate)

Die Einheit steht selten genau mit Mikrofon 0 nach Nord. Der Nordabgleich korrigiert die Peilung um einen Offset (Kommando Id 9, ICD 4.4):

1. Drehschalter auf **Calibrate**. Das Board verarbeitet dann wie in Detect.
2. Eine Referenzquelle in bekannter Richtung betreiben, zum Beispiel einen Lautsprecher oder eine schwebende Drohne. Ihren Azimut eintragen (0° = Nord, im Uhrzeigersinn).
3. **Messung starten.** Die Peilungen der UnitReports werden über die Messdauer zirkular gemittelt. Angezeigt werden:
   - Mittel und Streuung
   - Abweichung zur Referenz
   - vorgeschlagener Offset
   - eine Warnung bei weniger als 10 Peilungen oder mehr als 5° Streuung
4. **Übernehmen** sendet den Offset. Er wird gespeichert (QSettings) und bei jedem Verbinden erneut gesendet. **Offset 0** hebt den Abgleich auf.

![Calibrate](docs/gui_calibrate.png)

## Tests (ohne Hardware)

```
pip install pytest
python -m pytest tests
```

- **Plattform:** `test_loopback.py` benutzt einen virtuellen seriellen Port (pty) und läuft nur unter Linux/macOS.
- **Ohne Bildschirm:** Auf Linux vorher `QT_QPA_PLATFORM=offscreen` setzen.
- **GitHub Actions:** führt die Tests bei jedem Push auf `main` und bei jedem Pull Request aus (`.github/workflows/tests.yml`, Python 3.10 und 3.12).

## Werkzeuge für die Hardware

In `tools/`, nicht Teil der Tests:

- `python -m tools.hw_reader COM5`: Rohbytes eines Ports ausgeben.
- `python -m tools.hw_writer COM5`: Mode DETECT senden und die erste Antwort ausgeben.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `app/main.py` | Einstieg, Ausnahmebehandlung |
| `app/gui/main_window.py` | Hauptfenster: Verbindung, Queues, Tracking, Einstellungen |
| `app/widgets/` | Bedienfeld links (Drehschalter, Schalter), Statusfenster |
| `app/tabs/` | Tabs Detect, Read, Calibrate |
| `app/usb/` | Reader, Writer, Parser (Resync, CRC), Nachrichten |
| `app/model/SDSUSBModel.py` | Queues, Zähler, Kommandos PC → SDS |
| `app/tracking/` | Tracking-Einheit (Kalman, Gate, ŝ), Feedback Id 8 |
| `app/calibration.py` | Nordabgleich: zirkulares Mittel, Offset |
| `app/geo.py` | Standort: Eingabe prüfen, Kodierung, Ost/Nord → Breite/Länge |

## Dokumente

- `docs/Analyse_ToDo.md`: Analyse, Befunde und ToDo-Liste
- `docs/Traceability_FSL9_PC.md`: Abgleich mit dem Patent FSL9 (Processing Module 120 auf dem PC, Tracking-Einheit 150)
