"""
Protokoll PC -> SDS gegen die ICD (SDS_110 doc/ICD_SDS_PC_Monitor.md), ohne Hardware.
Aufruf: python -m pytest tests/test_protocol.py
"""
import zlib

from app.model.SDSUSBModel import SDSMode, SDSUSBModel


def test_mode_values_match_firmware():
    # Firmware SDS_Structs.hpp: DETECT = 1, CALIBRATE = 2, READ = 3
    assert (SDSMode.DETECT, SDSMode.CALIBRATE, SDSMode.READ) == (1, 2, 3)


def test_mode_message_layout_and_crc():
    m = SDSUSBModel()
    pkt = m.build_mode_message(int(SDSMode.READ))
    assert len(pkt) == 16
    assert pkt[:8] == bytes.fromhex("DEADBEEF02000010")
    assert pkt[8:12] == bytes.fromhex("00000003")
    assert pkt[12:] == (zlib.crc32(pkt[:12]) & 0xFFFFFFFF).to_bytes(4, "big")


def test_simulation_message():
    m = SDSUSBModel()
    assert m.build_simulation_message(1)[:12] == bytes.fromhex("DEADBEEF030000100000 0001".replace(" ", ""))
    assert m.build_simulation_message(0)[8:12] == bytes(4)


def test_sent_statistics_any_id():
    m = SDSUSBModel()
    m.update_sent(6, b"x")
    m.update_sent(42, b"y")
    assert m.stats_sent_total == 2 and m.stats_sent_by_id[6] == 1 and m.stats_sent_by_id[42] == 1
