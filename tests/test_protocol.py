"""
Protokoll PC -> SDS gegen die ICD (SDS_110 doc/ICD_SDS_PC_Monitor.md), ohne Hardware.
Aufruf: python -m pytest tests/test_protocol.py
"""
import zlib

import pytest

from app.model.SDSUSBModel import SDSMode, SDSUSBModel, SIM_SCENARIOS


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


def test_simulation_scenarios_match_firmware():
    # Firmware Harness/SimScenario.hpp: 1 Standard, 2 + k Szenario k (DroneSweep … FlyBy)
    assert SIM_SCENARIOS == ((1, "Standard (Firmware)"), (2, "DroneSweep"), (3, "DroneStatic"),
                             (4, "SingleTone"), (5, "WindNoise"), (6, "Silence"), (7, "FlyBy"))
    m = SDSUSBModel()
    pkt = m.build_simulation_message(7)
    assert pkt[:12] == bytes.fromhex("DEADBEEF03000010" "00000007")
    assert pkt[12:] == (zlib.crc32(pkt[:12]) & 0xFFFFFFFF).to_bytes(4, "big")
    for bad in (8, -1, 100):
        with pytest.raises(ValueError):
            m.build_simulation_message(bad)


def test_sent_statistics_any_id():
    m = SDSUSBModel()
    m.update_sent(6, b"x")
    m.update_sent(42, b"y")
    assert m.stats_sent_total == 2 and m.stats_sent_by_id[6] == 1 and m.stats_sent_by_id[42] == 1


def test_sync_message_matches_icd_example():
    # ICD 4.2: 28.09.2026 12:00:00 UTC, 21,50 °C
    pkt = SDSUSBModel().build_sync_message(1790596800 * 1_000_000, 21.5)
    assert pkt == bytes.fromhex("DEADBEEF07000018 00065C89CE333000 0866 0000 01B1FFD4".replace(" ", ""))


def test_sync_message_unknown_and_negative_temperature():
    m = SDSUSBModel()
    assert m.build_sync_message(0, None)[16:18] == bytes.fromhex("8000")
    assert m.build_sync_message(0, -5.5)[16:18] == (-550).to_bytes(2, "big", signed=True)


def test_sync_temperature_out_of_range():
    import pytest
    with pytest.raises(ValueError):
        SDSUSBModel().build_sync_message(0, 61.0)


def test_unit_id_and_srp_messages():
    m = SDSUSBModel()
    assert m.build_unit_id_message(0x1ABCD)[:12] == bytes.fromhex("DEADBEEF050000100000ABCD")
    assert m.build_srp_message(True)[:12] == bytes.fromhex("DEADBEEF0600001000000001")
    assert m.build_srp_message(False)[8:12] == bytes(4)
