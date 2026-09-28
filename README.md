# PC-Monitor für SDS_110

GUI für die Sensoreinheit SDS_110 (STM32F746) über USB-CDC: Betriebsart und Signalquelle
steuern, Peilungen (Detect) und Rohdaten (Read) anzeigen, Status und Fehler protokollieren.
Das Nachrichtenformat beschreibt SDS_110 `doc/ICD_SDS_PC_Monitor.md`.

## Start

```
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Bedienung

- **Links:** Port wählen, Schalter **On** verbindet. Beim Verbinden werden die Signalquelle (Real/Simulation) und die Betriebsart gesendet.
- **Drehschalter Detect – Read – Calibrate:** wählt die Betriebsart des Boards und den angezeigten Tab.
- **Board:** Unit-ID setzen, SRP-Referenzscan aus/ein.
- **Sync:** UTC und Lufttemperatur. Wird beim Verbinden, jede Minute und bei Änderung der Temperatur gesendet; ohne Haken bei „Temp.“ gilt die Temperatur als unbekannt.
- **Unten:** Status- und Fehlermeldungen mit Zählern RX/TX/Fehler, dazu die Meldungen des Boards (Logger) als „SDS: …“.

![GUI](docs/gui_detect.png)

## Tests (ohne Hardware)

```
pip install pytest
python -m pytest tests
```

`test_loopback.py` benutzt einen virtuellen seriellen Port (pty) und läuft nur unter Linux/macOS.
Auf Linux ohne Bildschirm vorher `QT_QPA_PLATFORM=offscreen` setzen. `tests/test_reader.py` und
`test_writer.py` sind Hilfsskripte für einen echten Port (COM5).

## Dokumente

- `docs/Analyse_ToDo.md`: Analyse, Befunde P1–P19, ToDo-Liste
- `docs/Traceability_FSL9_PC.md`: Abgleich mit dem Patent FSL9 (Processing Module 120 auf dem PC, Tracking-Einheit 150)
