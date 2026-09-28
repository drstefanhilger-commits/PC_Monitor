# PC-Monitor – Traceability gegen FSL9

- **Stand:** 28.09.2026.
- **Geprüft:** PC-Monitor nach GUI-Redesign (`main` 627b13d) und T1–T3.
- **Grundlage:** FSL9 (SDS_110 `doc/Stefan_FSL9.docx`) und die Aufgabenteilung aus SDS_110 `Core/SDS_110/README.md`:
  - **Komponente A** (Processing Module 120 auf dem PC): Inter-Unit-Teil von 126, Lokalisation 128, Candidate Report 130.
  - **Komponente B** (Tracking-Einheit 150): 152–162 und das Feedback.
- **Firmware-Seite:** SDS_110 `doc/Traceability_FSL9.md` (A1–A36).

## Zusammenfassung

Von 25 Anforderungen an den PC-Monitor sind 7 erfüllt, 3 teilweise erfüllt, 14 nicht erfüllt und 1 nicht im Umfang (Stand nach T1–T5).

- Der PC-Monitor ist heute eine Anzeige für **eine** Einheit. Er steuert Betriebsart, Signalquelle, Unit-ID und SRP, sendet UTC und Temperatur (Sync) und zeigt Detect-Frame und UnitReport an: UTC in µs, Paare, Residuum, Bänder mit p_b.
- Die patentwesentlichen PC-Funktionen fehlen vollständig:
  - Lokalisation mit mehreren Einheiten (§6),
  - Candidate Report (§7),
  - Tracking-Einheit mit doppeltem Konsistenz-Gate (§8–9, Ansprüche 6, 7, 11),
  - Feedback an die Firmware (§10, Anspruch 8).
- **Architekturfrage für §5 und §6:** Die Inter-Unit-GCC-PHAT braucht die Spektren bzw. die Signale mehrerer Einheiten an einem Ort. Der UnitReport überträgt nur Peilung, Residuum, Pegel und die Bänder mit p_b. Vor T7 muss feststehen, ob die Firmware Spektren der selektierten Bins überträgt oder ob die Einheiten ihre TDOA zu einer Master-Einheit bilden.

## Matrix

Status: Erfüllt · Teilweise · Nicht erfüllt · Offen (Festlegung fehlt) · Nicht im Umfang.
Code-Referenzen beziehen sich auf `app/`.

| ID | FSL9 | Anforderung | Zugesichert | Ist | Code-Referenz | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | §1, A6 | Zeitbezug der Einheiten | UTC, Synchronisation ≤ 10 µs | Sync Id 7 mit UTC in µs beim Verbinden, jede Minute und per Knopf (über USB ~1 ms genau); ≤ 10 µs erst mit GNSS-PPS (HW-Version 2) | `gui/main_window.py send_sync`, `model/SDSUSBModel.py build_sync_message` | Teilweise |
| P2 | §5, A23 | Temperatur für c | c temperaturkorrigiert | Temperatur als Eingabe im Bedienfeld (−40…+60 °C), gesendet in Id 7; kein Sensor | `widgets/control_panel.py temperature`, `model/SDSUSBModel.py build_sync_message` | Teilweise |
| P3 | §1, §6 | Positionen der Einheiten | vermessen auf 0,1 m, gespeichert | keine Konfiguration von Einheiten | – | Nicht erfüllt |
| P4 | §5, Anspr. 1(e), 10 | Inter-Unit-GCC-PHAT | Korrelation zwischen Einheiten mit gemeinsamer Selektion und Gewichten | nicht vorhanden; die Daten dafür werden nicht übertragen (Architekturfrage) | – | Nicht erfüllt |
| P5 | §6(a) | Multilateration | N ≥ 3: Hyperbeln \|x − u_i\| − \|x − u_j\| = c·τ_ij, gewichtete LS, Gewicht = Peak-Ratio | nicht vorhanden | – | Nicht erfüllt |
| P6 | §6(b) | Gemeinsamer Modus | N = 2: eine Hyperbel + zwei Peilungen, gewichtete LS | nicht vorhanden; die Peilungen im UnitReport Id 5 werden nicht gelesen | – | Nicht erfüllt |
| P7 | §6, FIG. 5 | Referenzpunkt und Azimut | Zentroid der Einheiten, φ ab Nord | Azimut 0° = Nord, im Uhrzeigersinn, Mikrofon 0 = Nord in Firmware und Lageplan (Nord oben, Ost rechts); Referenzpunkt = Array (eine Einheit, gleich dem Zentroid); Zentroid mehrerer Einheiten mit T7 | `tabs/tab_detect.py compass_xy`, SDS_110 `Azimuth.hpp` | Erfüllt |
| P8 | §6 | Kein Kandidat ohne ausreichende TDOA | bei < 2 unabhängigen TDOA (a) bzw. fehlender Peilung (b) keine Position | Lokalisation fehlt (P5, P6) | – | Nicht erfüllt |
| P9 | §7, Anspr. 1(g) | Candidate Report: Zeit | UTC, µs | UnitReport Id 5: time_us (u64) mit Zeitquelle, angezeigt als UTC mit µs bzw. Laufzeit | `usb/messages.py parse_unit_report, time_text`, `tabs/tab_detect.py update_unit_report` | Erfüllt |
| P10 | §7 | Candidate Report: Ort | φ und r | φ und r aus Detect Id 1 angezeigt; r aus dem Pegelmodell einer Einheit, nicht aus TDOA | `tabs/tab_detect.py update_frame` | Teilweise |
| P11 | §7 | Candidate Report: Qualität | Zahl akzeptierter Paare, LS-Residuum | Paare und Residuum aus Id 5 angezeigt; Konfidenz aus Id 1 | `tabs/tab_detect.py update_unit_report` | Erfüllt |
| P12 | §7 | Candidate Report: akustischer Zustand | Bandindizes und p_b der selektierten Bänder | Bandindizes und p_b aus Id 5 als Text und Balkendiagramm über 64 Bänder; Zustandsvektor mit 0 für nicht selektierte Bänder | `usb/messages.py state_vector`, `tabs/tab_detect.py` | Erfüllt |
| P13 | §7 | Feste Binärstruktur, ~30 Reports/s | feste Struktur je Frame | feste Strukturen für Id 1, 2, 5, 99 mit Längenprüfung je Id, CRC-Prüfung und Byte-Resync (Tests `test_parser.py`) | `usb/sds_parser.py`, `usb/usb_reader.py` | Erfüllt |
| P14 | §8 | Referenzzustand ŝ | ŝ ← (1 − α)ŝ + αs, α = 0,2, fehlende Bänder = 0 | nicht vorhanden | – | Nicht erfüllt |
| P15 | §8 | Kinematischer Zustand | letzte Position, v, Zeit; Kalman-Filter mit konstanter Geschwindigkeit | nicht vorhanden | – | Nicht erfüllt |
| P16 | §9(i), Anspr. 6(c)(i) | Akustisches Gate | Kosinus-Ähnlichkeit σ > θ_sim = 0,7 | nicht vorhanden | – | Nicht erfüllt |
| P17 | §9(ii), Anspr. 6(c)(ii) | Räumlich-zeitliches Gate | Mahalanobis-Distanz < χ²₂,₀.₉₉ | nicht vorhanden | – | Nicht erfüllt |
| P18 | §9, Anspr. 6(d) | Übernahme nur bei beiden Kriterien | sonst verwerfen, Filter nur Prädiktion | nicht vorhanden | – | Nicht erfüllt |
| P19 | §9, Anspr. 7 | Start und Ende einer Spur | Start nach 3 aufeinanderfolgenden Reports, Ende nach 2 s ohne Report | nicht vorhanden | – | Nicht erfüllt |
| P20 | §9, 162, Anspr. 6(e), 11 | Ausgabe der Trajektorie | Azimut, Distanz, Geschwindigkeit an ein externes System, mit Report-Rate | nur der letzte Punkt und Verläufe von Distanz und Konfidenz werden angezeigt; keine Spur, keine Ausgabe | `tabs/tab_detect.py` | Nicht erfüllt |
| P21 | §10, Anspr. 8, 9(c), 12 | Feedback an die Firmware | nach jeder Übernahme ŝ und die vorhergesagte Position (Id 8, noch festzulegen) | nicht vorhanden; die Firmware hat `applyFeedback`, aber kein USB-Kommando dafür | – | Nicht erfüllt |
| P22 | §12, FIG. 6 | Trennung Erkennung ↔ Tracking | zwei Funktionen mit definierter Schnittstelle, auch als Software-Module auf einer Plattform zulässig | Schnittstelle 140 = ICD (USB). Auf dem PC gibt es keine Trennung in Komponente A und B, weil beide fehlen. | SDS_110 `doc/ICD_SDS_PC_Monitor.md` | Nicht erfüllt |
| P23 | ICD | Steuerung des Boards | Betriebsart (Id 2), Signalquelle (Id 3) mit den Werten der Firmware | Drehschalter und Schalter senden Id 2 und 3 mit den Firmware-Werten und gültiger CRC; beim Verbinden wird der Stand der Schalter gesendet (Tests `test_gui.py`, `test_loopback.py`) | `gui/main_window.py on_mode, on_simulation, connect_usb` | Erfüllt |
| P24 | ICD, §11 | Anzeige von Fehlern | fehlerhafte Frames erkennen und melden | Resync, falsche Länge, CRC-Fehler und unbekannte Ids erscheinen im Status-Fenster mit Zählern | `usb/sds_parser.py`, `gui/main_window.py process_queue` | Erfüllt |
| P25 | Anspr. 14 | Programm der Tracking-Einheit | computerlesbares Medium | betrifft die Patentform, kein Softwaremerkmal | – | Nicht im Umfang |

Die Zeilen P23 und P24 stammen aus der ICD und nicht aus FSL9. Die Zählung in der Zusammenfassung enthält sie, um den Stand des Programms vollständig abzubilden.

## Maßnahmen

| Prio | IDs | Maßnahme | ToDo |
| --- | --- | --- | --- |
| 1 | P9–P13 | erledigt: UnitReport Id 5 lesen und anzeigen, Reader mit Resync und CRC | T1, T2 |
| 2 | P1, P2 | erledigt: Sync Id 7 mit UTC und Temperatur; offen: Temperatursensor, GNSS-PPS (HW-Version 2) | T3 |
| 3 | P7 | erledigt: Azimut ab Nord im Uhrzeigersinn in Firmware und Plot | T5 |
| 4 | P14–P21 | Tracking-Einheit als eigenes Modul (Komponente B), zunächst mit Reports **einer** Einheit (Peilung + Pegel-Distanz); Feedback Id 8 zusammen mit der Firmware festlegen | T8 |
| 5 | P3–P6, P8, P22 | Mehrere Einheiten und Lokalisation (Komponente A); vorher die Architekturfrage klären | T7 |
