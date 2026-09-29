# PC-Monitor – Traceability gegen FSL9

- **Stand:** 28.09.2026.
- **Geprüft:** PC-Monitor nach GUI-Redesign (`main` 627b13d) und T1–T11 (ohne T7).
- **Grundlage:** FSL9 (SDS_110 `doc/Stefan_FSL9.docx`) und die Aufgabenteilung aus SDS_110 `Core/SDS_110/README.md`:
  - **Komponente A** (Processing Module 120 auf dem PC): Inter-Unit-Teil von 126, Lokalisation 128, Candidate Report 130.
  - **Komponente B** (Tracking-Einheit 150): 152–162 und das Feedback.
- **Firmware-Seite:** SDS_110 `doc/Traceability_FSL9.md` (A1–A36).

## Zusammenfassung

Von 25 Anforderungen an den PC-Monitor sind 14 erfüllt, 6 teilweise erfüllt, 4 nicht erfüllt und 1 nicht im Umfang (Stand nach T1–T11 und Standort).

- Der PC-Monitor ist heute eine Anzeige für **eine** Einheit. Er steuert Betriebsart, Signalquelle, Unit-ID und SRP, sendet UTC und Temperatur (Sync) und zeigt Detect-Frame und UnitReport an: UTC in µs, Paare, Residuum, Bänder mit p_b.
- Die Tracking-Einheit (Komponente B, §8–10) ist umgesetzt (T8). Es fehlen noch:
  - Lokalisation mit mehreren Einheiten (§6, Komponente A),
  - eine laufende Ausgabe der Trajektorie an ein externes System (§9, 162),
  - die Nutzung der Vorhersage im Board für das TDOA-Suchfenster (§10, Firmware A34).
- **Architektur für §5 und §6: entschieden am 28.09.2026, „nur TDOA übertragen“.**
  - Jede Einheit sendet ihre Intra-Unit-Ergebnisse: TDOA der Paare bzw. Peilung, Qualität und µs-Zeit. Spektren und Signale werden nicht übertragen.
  - **Folge:** Die Inter-Unit-GCC-PHAT (P4) entfällt als bewusste Abweichung von FSL9.
  - Die Lokalisation mehrerer Einheiten (P5, P6) erfolgt aus den Peilungen und µs-Zeitstempeln der Einheiten, also über Kreuzpeilung und die Zeitdifferenzen gleicher Ereignisse.
  - Die Bandbreite bleibt klein (≈ 144 B je Frame).

## Matrix

Status: Erfüllt · Teilweise · Nicht erfüllt · Offen (Festlegung fehlt) · Nicht im Umfang.
Code-Referenzen beziehen sich auf `app/`.

| ID | FSL9 | Anforderung | Zugesichert | Ist | Code-Referenz | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | §1, A6 | Zeitbezug der Einheiten | UTC, Synchronisation ≤ 10 µs | Sync Id 7 mit UTC in µs beim Verbinden, jede Minute und per Knopf (über USB ~1 ms genau); ≤ 10 µs erst mit GNSS-PPS (HW-Version 2) | `gui/main_window.py send_sync`, `model/SDSUSBModel.py build_sync_message` | Teilweise |
| P2 | §5, A23 | Temperatur für c | c temperaturkorrigiert | Temperatur als Eingabe im Bedienfeld (−40…+60 °C), gesendet in Id 7; kein Sensor | `widgets/control_panel.py temperature`, `model/SDSUSBModel.py build_sync_message` | Teilweise |
| P3 | §1, §6 | Positionen der Einheiten | vermessen auf 0,1 m, gespeichert | Position einer Einheit lokal (Ost, Nord, Oben in mm, Ursprung [0, 0, 0]) eingeben, speichern, beim Verbinden senden (Id 10), Rückmeldung des Boards (Id 6); Spur im CSV auch im lokalen System. Mehrere Einheiten mit T7 | `local_position.py`, `gui/main_window.py on_position`, `widgets/control_panel.py` | Teilweise |
| P4 | §5, Anspr. 1(e), 10 | Inter-Unit-GCC-PHAT | Korrelation zwischen Einheiten mit gemeinsamer Selektion und Gewichten | entfällt nach der Entscheidung „nur TDOA übertragen“ (28.09.2026): keine Spektren zwischen den Einheiten; Ersatz über Peilungen und µs-Zeiten (T7) | – | Nicht erfüllt (bewusste Abweichung) |
| P5 | §6(a) | Multilateration | N ≥ 3: Hyperbeln \|x − u_i\| − \|x − u_j\| = c·τ_ij, gewichtete LS, Gewicht = Peak-Ratio | nicht vorhanden | – | Nicht erfüllt |
| P6 | §6(b) | Gemeinsamer Modus | N = 2: eine Hyperbel + zwei Peilungen, gewichtete LS | nicht vorhanden; die Peilungen im UnitReport Id 5 werden nicht gelesen | – | Nicht erfüllt |
| P7 | §6, FIG. 5 | Referenzpunkt und Azimut | Zentroid der Einheiten, φ ab Nord | Azimut 0° = Nord, im Uhrzeigersinn, Mikrofon 0 = Nord in Firmware und Lageplan (Nord oben, Ost rechts); Referenzpunkt = Array (eine Einheit, gleich dem Zentroid); Nordabgleich der aufgestellten Einheit mit einer Referenzquelle (Tab Calibrate, Id 9, T10); Zentroid mehrerer Einheiten mit T7 | `tabs/tab_detect.py compass_xy`, `calibration.py`, `tabs/tab_calibrate.py`, SDS_110 `Azimuth.hpp` | Erfüllt |
| P8 | §6 | Kein Kandidat ohne ausreichende TDOA | bei < 2 unabhängigen TDOA (a) bzw. fehlender Peilung (b) keine Position | Lokalisation fehlt (P5, P6) | – | Nicht erfüllt |
| P9 | §7, Anspr. 1(g) | Candidate Report: Zeit | UTC, µs | UnitReport Id 5: time_us (u64) mit Zeitquelle, angezeigt als UTC mit µs bzw. Laufzeit | `usb/messages.py parse_unit_report, time_text`, `tabs/tab_detect.py update_unit_report` | Erfüllt |
| P10 | §7 | Candidate Report: Ort | φ und r | φ und r aus Detect Id 1 angezeigt; r aus dem Pegelmodell einer Einheit, nicht aus TDOA | `tabs/tab_detect.py update_frame` | Teilweise |
| P11 | §7 | Candidate Report: Qualität | Zahl akzeptierter Paare, LS-Residuum | Paare und Residuum aus Id 5 angezeigt; Konfidenz aus Id 1 | `tabs/tab_detect.py update_unit_report` | Erfüllt |
| P12 | §7 | Candidate Report: akustischer Zustand | Bandindizes und p_b der selektierten Bänder | Bandindizes und p_b aus Id 5 als Text und Balkendiagramm über 64 Bänder; Zustandsvektor mit 0 für nicht selektierte Bänder | `usb/messages.py state_vector`, `tabs/tab_detect.py` | Erfüllt |
| P13 | §7 | Feste Binärstruktur, ~30 Reports/s | feste Struktur je Frame | feste Strukturen für Id 1, 2, 5, 99 mit Längenprüfung je Id, CRC-Prüfung und Byte-Resync (Tests `test_parser.py`) | `usb/sds_parser.py`, `usb/usb_reader.py` | Erfüllt |
| P14 | §8 | Referenzzustand ŝ | ŝ ← (1 − α)ŝ + αs, α = 0,2, fehlende Bänder = 0 | ŝ ← 0,8·ŝ + 0,2·s über 64 Bänder, nicht selektierte Bänder = 0 (Test `test_reference_state_ema`) | `tracking/tracker.py` Tracker.process | Erfüllt |
| P15 | §8 | Kinematischer Zustand | letzte Position, v, Zeit; Kalman-Filter mit konstanter Geschwindigkeit | Kalman-Filter mit konstanter Geschwindigkeit in (Ost, Nord), Zustand [x, y, vx, vy]; Messkovarianz aus σ_φ = 3° und σ_r = 30 % (Pegelmodell); Test: 10 m/s ± 2 m/s nach 5 s | `tracking/tracker.py` Tracker, measurement_cov | Erfüllt |
| P16 | §9(i), Anspr. 6(c)(i) | Akustisches Gate | Kosinus-Ähnlichkeit σ > θ_sim = 0,7 | Kosinus-Ähnlichkeit σ(s, ŝ) > 0,7; Störquelle mit anderem Spektrum an der vorhergesagten Position wird verworfen (Test) | `tracking/tracker.py` cosine, THETA_SIM | Erfüllt |
| P17 | §9(ii), Anspr. 6(c)(ii) | Räumlich-zeitliches Gate | Mahalanobis-Distanz < χ²₂,₀.₉₉ | Mahalanobis-Distanz² der Innovation < 9,21 (χ²₂,₀.₉₉); gleiches Spektrum 120° daneben wird verworfen (Test) | `tracking/tracker.py` CHI2_2_099 | Erfüllt |
| P18 | §9, Anspr. 6(d) | Übernahme nur bei beiden Kriterien | sonst verwerfen, Filter nur Prädiktion | Übernahme (Kalman-Update, ŝ-Update) nur bei beiden Kriterien; sonst verworfen, Filter nur Prädiktion; Anzeige σ, d² und Grund | `tracking/tracker.py` Tracker.process | Erfüllt |
| P19 | §9, Anspr. 7 | Start und Ende einer Spur | Start nach 3 aufeinanderfolgenden Reports, Ende nach 2 s ohne Report | vorläufige Spur aus dem ersten Report, bestätigt nach 3 aufeinanderfolgenden Reports (der erste zählt mit), Unterbrechung beginnt neu; Ende nach 2 s ohne Übernahme, auch wenn keine Reports mehr kommen | `tracking/tracker.py` N_INIT, T_END_S; `gui/main_window.py check_track_timeout` | Erfüllt |
| P20 | §9, 162, Anspr. 6(e), 11 | Ausgabe der Trajektorie | Azimut, Distanz, Geschwindigkeit an ein externes System, mit Report-Rate | bestätigte Trajektorie im Lageplan (grün, Vorhersage als Ring), Geschwindigkeit und Kurs; Export als CSV; keine laufende Ausgabe an ein externes System | `tabs/tab_detect.py update_track`, `gui/main_window.py export_track` | Teilweise |
| P21 | §10, Anspr. 8, 9(c), 12 | Feedback an die Firmware | nach jeder Übernahme ŝ und die vorhergesagte Position (Id 8, noch festzulegen) | Feedback Id 8 (ŝ + Vorhersage für das nächste Intervall) nach jeder Übernahme der bestätigten Spur, Zurücksetzen bei Spurende; Firmware wendet ŝ an und setzt nach 2 s zurück (SDS_110 t_feedback); die Vorhersage nutzt die Firmware noch nicht (A34) | `tracking/feedback.py`, `gui/main_window.py track_report` | Erfüllt |
| P22 | §12, FIG. 6 | Trennung Erkennung ↔ Tracking | zwei Funktionen mit definierter Schnittstelle, auch als Software-Module auf einer Plattform zulässig | Tracking-Einheit als eigenes Modul ohne Qt (`app/tracking/`), Eingang = Candidate Reports, Ausgang = Trajektorie und Feedback; Komponente A (Lokalisation mehrerer Einheiten) fehlt | `tracking/`, SDS_110 `doc/ICD_SDS_PC_Monitor.md` | Teilweise |
| P23 | ICD | Steuerung des Boards | Betriebsart (Id 2), Signalquelle (Id 3) mit den Werten der Firmware, Simulator-Szenario 1 … 7 | Drehschalter und Schalter senden Id 2 und 3 mit den Firmware-Werten und gültiger CRC; das Szenario wird gespeichert; beim Verbinden wird der Stand der Schalter gesendet (Tests `test_gui.py`, `test_loopback.py`, `test_protocol.py`) | `gui/main_window.py on_mode, on_simulation, connect_usb` | Erfüllt |
| P24 | ICD, §11 | Anzeige von Fehlern | fehlerhafte Frames erkennen und melden | Resync, falsche Länge, CRC-Fehler und unbekannte Ids erscheinen im Status-Fenster mit Zählern | `usb/sds_parser.py`, `gui/main_window.py process_queue` | Erfüllt |
| P25 | Anspr. 14 | Programm der Tracking-Einheit | computerlesbares Medium | betrifft die Patentform, kein Softwaremerkmal | – | Nicht im Umfang |

Die Zeilen P23 und P24 stammen aus der ICD und nicht aus FSL9. Die Zählung in der Zusammenfassung enthält sie, um den Stand des Programms vollständig abzubilden.

## Maßnahmen

| Prio | IDs | Maßnahme | ToDo |
| --- | --- | --- | --- |
| 1 | P9–P13 | erledigt: UnitReport Id 5 lesen und anzeigen, Reader mit Resync und CRC | T1, T2 |
| 2 | P1, P2 | erledigt: Sync Id 7 mit UTC und Temperatur; offen: Temperatursensor, GNSS-PPS (HW-Version 2) | T3 |
| 3 | P7 | erledigt: Azimut ab Nord im Uhrzeigersinn in Firmware und Plot; Nordabgleich (Id 9) | T5, T10 |
| 4 | P14–P21 | erledigt: Tracking-Einheit als eigenes Modul, Feedback Id 8 (PC und Firmware); offen: Ausgabe an ein externes System, Vorhersage in der Firmware nutzen (A34) | T8 |
| 5 | P3–P6, P8, P22 | Mehrere Einheiten und Lokalisation (Komponente A) mit „nur TDOA übertragen“: Kreuzpeilung, Zeitdifferenzen aus µs-Zeiten | T7 |
