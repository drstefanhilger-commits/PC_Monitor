# PC-Monitor – Analyse und ToDo-Liste

- **Stand:** 28.09.2026.
- **Analysiert:** Stand `main` 7d1b7de („07-09-1“).
- **Bezüge:**
  - Schnittstelle: SDS_110 `doc/ICD_SDS_PC_Monitor.md`
  - Patent: FSL9 (SDS_110 `doc/Stefan_FSL9.docx`)
  - Traceability der Firmware: SDS_110 `doc/Traceability_FSL9.md`
- **Umgesetzt in diesem Stand:** GUI-Redesign (Abschnitt 3) sowie die Befunde P1, P2, P11 (Log-Flut) und P13–P15. Die übrigen Befunde sind offen und in der ToDo-Liste (Abschnitt 4) eingeplant.

## 1. Aufbau

| Teil | Dateien | Aufgabe |
| --- | --- | --- |
| Start | `app/main.py` | QApplication, MainWindow |
| Hauptfenster | `app/gui/main_window.py` | Layout, USB-Verbindung, Queue-Polling mit 50 Hz |
| Modell | `app/model/SDSUSBModel.py` | Queues, Zähler, Aufbau der Kommandos PC → SDS |
| USB | `app/usb/usb_reader.py`, `usb_writer.py` | QThreads: Frames lesen und in Queues legen, Kommandos schreiben |
| USB (ungenutzt) | `app/usb/sds_parser.py`, `usb_port_manager.py` | Byte-Resync und CRC-Prüfung; Port-Verwaltung |
| Tabs | `app/tabs/tab_detect.py`, `tab_read.py`, `tab_calibrate.py` | Anzeige je Betriebsart |
| Bedienelemente | `app/widgets/control_panel.py`, `mode_dial.py`, `toggle_switch.py`, `status_panel.py` | Bedienfeld links, Status unten |
| Altbestand | `Safe/`, `srp_monitor.py`, `app/gui/sds_read_usb_receiver_gui.py` | frühere Versionen mit altem Protokoll, nicht lauffähig bzw. nicht eingebunden |

Datenfluss: Der `USBReader` liest einen 8-Byte-Kopf, danach den Rest laut Länge, und legt das Frame nach Id in `detect_queue`, `read_queue` oder `inspect_queue`. Das Hauptfenster leert die Queues alle 20 ms und verteilt die Frames an die Tabs.

## 2. Befunde

Status: **behoben** = in diesem Stand umgesetzt und getestet, **offen** = in der ToDo-Liste eingeplant.

| Nr. | Prio | Befund | Folge | Status |
| --- | --- | --- | --- | --- |
| P1 | hoch | `SDSMode` hatte READ = 2 und CALIBRATE = 3; die Firmware erwartet CALIBRATE = 2 und READ = 3 | Der Drehschalter auf READ hat CALIBRATE geschickt und umgekehrt. Das ist die Ursache von SDS_110 Befund 25. | behoben (`SDSUSBModel.py`) |
| P2 | hoch | Die CRC der Kommandos war fest `12 34 56 78` | Sobald die Firmware die CRC prüft (SDS_110 Befund 12), würde sie jedes Kommando verwerfen | behoben: CRC32 wie zlib, big-endian (ICD 3) |
| P3 | hoch | Findet der Reader das Magic nicht, verwirft er 8 Byte und liest den nächsten Kopf | Ist der Datenstrom um k Byte versetzt, bleibt er versetzt, und alle folgenden Frames gehen verloren. Der vorhandene `SDSParser` synchronisiert Byte für Byte, wird aber nicht benutzt. | offen (T1) |
| P4 | hoch | Empfangene Frames werden ohne CRC-Prüfung angenommen | Gestörte Frames werden angezeigt | offen (T1) |
| P5 | hoch | Die Länge aus `len_id` wird nicht geprüft | Bei einer Länge < 8 wird mit negativer Länge gelesen; bei großen Werten blockiert das Lesen bzw. es werden Frames verschluckt | offen (T1) |
| P6 | hoch | UnitReport (Id 5) und Logger (Id 99) sind unbekannt und werden als Fehler gezählt | µs-Zeit, Zeitquelle, Paare, Residuum, Bänder und p_b sowie die Meldungen der Firmware werden nicht angezeigt | offen (T2) |
| P7 | hoch | Es fehlen die Kommandos Sync (Id 7: UTC und Temperatur), Unit-ID (5) und SRP-Referenz (6). Id 1 sendet immer 0. | kein UTC-Bezug, Schallgeschwindigkeit bleibt 343 m/s (FSL9 A23), keine Einheiten-Kennung | Simulation (Id 3) behoben, Rest offen (T3) |
| P8 | mittel | Der Detect-Tab zeichnet x = d·sin φ, y = d·cos φ, also φ ab Nord im Uhrzeigersinn; die Firmware sendet φ ab der x-Achse gegen den Uhrzeigersinn | Das Ziel erscheint gespiegelt und gedreht (Firmware 90° wird rechts statt oben gezeichnet) | offen (T5), Konvention mit FSL9 A28 festlegen |
| P9 | mittel | Die Achsen im Detect-Tab sind fest (±100 m, 0–200 m); die Unit-ID wird ignoriert; es gibt keine Spur und keinen Verlauf | Ziele außerhalb von 100 m fallen aus dem Bild, mehrere Einheiten sind nicht unterscheidbar | offen (T5, T7) |
| P10 | hoch | Der Read-Tab teilt die 128 Werte in 8 Mikrofone × 16 auf. Tatsächlich enthält jede Nachricht 128 Samples **eines** Mikrofons (`micNr`) für Block `frameNr` 0…11. Die Werte werden als uint32 statt int32 gelesen. | Pegel und Werte sind falsch, negative Samples erscheinen als ~4·10⁹, der Hop wird nicht zusammengesetzt | offen (T4) |
| P11 | hoch | Bei READ kommen ~3000 Nachrichten/s. Der Reader meldete jedes Frame als Hex-Text, der Inspector baute bei jedem Frame seinen Text neu auf, und der Read-Tab setzt bei jedem Frame seinen Text | Die GUI friert ein, der Speicher wächst (Queues ohne Grenze) | Log-Flut behoben (`verbose=False`, Inspector ersetzt); Read-Tab-Takt und Queue-Grenzen offen (T4) |
| P12 | mittel | `serial.read()` mit 0,1 s Timeout kann den Rest eines Frames nur teilweise liefern | Meldung „payload_incomplete“ und danach Versatz (P3) | offen (T1) |
| P13 | niedrig | Der Inspector zählte unbekannte Ids als „corrupt“. Der Logger schrieb in dasselbe Textfeld, das der Inspector 50-mal pro Sekunde geleert hat. Die TX-Statistik kannte nur die Ids 1–3. | falsche Zähler, Meldungen verschwanden sofort | behoben (Status-Fenster, `update_sent` für alle Ids) |
| P14 | niedrig | Altbestand im Repository: `Safe/`, `srp_monitor.py` (tkinter, 24-Byte-Frames), `sds_read_usb_receiver_gui.py` (defekter Import), unbenutzte Teile (`STOP_REQUESTED`, `USBPortManager`) | Verwechslungsgefahr beim Weiterentwickeln | offen (T9) |
| P15 | niedrig | 25 `__pycache__`-Dateien im Repository, keine `requirements.txt`, Tests nur als Skripte gegen COM5 | Build nicht reproduzierbar, keine automatischen Tests | behoben: `.gitignore`, `requirements.txt`, Tests ohne Hardware |
| P16 | mittel | Wird USB getrennt, fängt der Reader die Ausnahme und versucht es endlos erneut; die GUI erfährt davon nichts | Die Anzeige bleibt „verbunden“ | offen (T6) |
| P17 | hoch | Die PC-Seite des Patents fehlt: Inter-Unit-Korrelation und Lokalisation (Teile von 126, 128), Candidate Report (130), Tracking-Einheit (150) und Feedback (Id 8) | FSL9 §6–10 und die Ansprüche 6–12 sind nicht umgesetzt (`Traceability_FSL9_PC.md`) | offen (T7, T8) |
| P18 | niedrig | Die Firmware hat in CALIBRATE keine Funktion | Der Calibrate-Tab bleibt ohne Daten | offen (T10) |
| P19 | mittel | Es kann nur ein COM-Port bzw. eine Einheit verbunden werden | FSL9 verlangt N ≥ 2 Einheiten | offen (T7) |

## 3. Umgesetzt: GUI-Redesign

![Detect](gui_detect.png)

- **Links:** ein Bedienfeld mit fester Breite, das alle Schalter enthält.
  - COM-Port mit Aktualisieren-Knopf.
  - Schalter **Off/On** öffnet und schließt die Verbindung. Schlägt das Öffnen fehl, springt der Schalter zurück auf Off.
  - Schalter **Real/Simulation** sendet ICD Id 3. Die Grundstellung ist Simulation wie in der Firmware.
  - Drehschalter **Detect – Read – Calibrate** (links, oben, rechts) sendet ICD Id 2.
- **Oben rechts:** die Tabs Detect, Read und Calibrate, links ausgerichtet. Sichtbar ist nur der Tab, den der Drehschalter wählt.
- **Unten:** das Status-/Fehlerfenster mit Zählerzeile (RX, Fehler, TX) und Meldungen mit Zeit und Stufe (INFO, WARN, ERROR, TX). Die Höhe lässt sich per Splitter ändern. Das Fenster ersetzt den Inspector-Tab.
- **Beim Verbinden** sendet der Monitor den Stand beider Schalter an das Board, sodass Board und GUI übereinstimmen. Ändert man die Schalter ohne Verbindung, werden sie beim nächsten Verbinden gesendet.

![Read](gui_read.png)

Tests ohne Hardware (`python -m pytest tests/test_protocol.py tests/test_gui.py tests/test_loopback.py`, 13 Tests):
- Kommando-Bytes und CRC nach ICD.
- Der Drehschalter wählt den Tab und sendet die Betriebsart.
- Schalter Simulation/Real.
- On ohne Port meldet einen Fehler.
- Fehler erscheinen im Status-Fenster.
- Verbindung über einen virtuellen seriellen Port (pty): On sendet Simulation und Mode, und ein Detect-Frame erreicht die Anzeige.

## 4. ToDo-Liste

| Nr. | Prio | Aufgabe | Befunde | Aufwand |
| --- | --- | --- | --- | --- |
| T1 | hoch | Den Reader auf `SDSParser` umstellen: Byte-Resync auf das Magic, Längengrenzen je Id, CRC prüfen, Zähler je Fehlerart | P3, P4, P5, P12 | klein |
| T2 | hoch | UnitReport Id 5 parsen: µs-Zeit und Quelle, Paare, Residuum, Bänder mit p_b, Anzeige im Detect-Tab (Balken p_b je Band). Logger Id 99 als INFO ins Status-Fenster. | P6 | mittel |
| T3 | hoch | Sync Id 7 senden: beim Verbinden und dann jede Minute, UTC in µs und Temperatur aus einem Eingabefeld (später Sensor). Außerdem Unit-ID Id 5 und einen Schalter SRP-Referenz Id 6 ins Bedienfeld. | P7 | klein |
| T4 | hoch | Den Read-Tab neu bauen: Hop aus 8 × 12 Blöcken zusammensetzen, int32 lesen, Pegel je Mikrofon in dBFS, Wellenform und Spektrum. Anzeige mit höchstens 10 Hz, Queues begrenzen. | P10, P11 | mittel |
| T5 | mittel | Azimut-Konvention mit der Firmware festlegen (FSL9 A28: ab Nord). Detect-Plot danach ausrichten, Achsen automatisch skalieren, Verlauf der Ziele. | P8, P9 | klein |
| T6 | mittel | Einen USB-Abbruch erkennen: Reader meldet den Abbruch, der Schalter geht auf Off, Fehlermeldung | P16 | klein |
| T7 | hoch | Mehrere Einheiten: je Einheit ein Port bzw. eine Unit-ID, Positionen konfigurierbar. PC-Teil von 126 und 128 (Multilateration N ≥ 3, gemeinsamer Modus N = 2) und Candidate Report (130). Dafür muss die Firmware Spektren oder TDOA je Einheit liefern (Architektur klären). | P17, P19 | groß |
| T8 | hoch | Tracking-Einheit (150) als eigenes Modul: ŝ mit α = 0,2, Kalman-Filter mit konstanter Geschwindigkeit, Kosinus > 0,7, χ²-Gate, Bestätigung nach 3 Reports, Ende nach 2 s, Ausgabe der Trajektorie, Feedback Id 8 an das Board | P17 | groß |
| T9 | niedrig | Altbestand entfernen oder nach `legacy/` verschieben; Hardware-Testskripte nach `tools/` | P14 | klein |
| T10 | niedrig | Inhalt des Calibrate-Tabs festlegen, sobald die Firmware CALIBRATE umsetzt (Pegel und Laufzeit je Mikrofon, Nordrichtung) | P18 | offen |
| T11 | niedrig | README (Start, Abhängigkeiten), Versionsnummer, Start-Skript für Windows; pytest in der CI | – | klein |
