import binascii

print("Running CRC test...")

hex_str = (
    "EFBEADDE"      # magic
    "14020002"      # len_id (len=532, id=2)
    "4E61BC00"      # timestamp = 12345678
    "0000"          # micNr
    "0000"          # frameNr
    + "00" * (128 * 4)  # payload (128 * uint32 = 512 bytes)
    + "1DFACD1C"    # CRC32 (little endian)
)

data = bytes.fromhex(hex_str)

crc_expected = int.from_bytes(data[-4:], "little")
crc_calc = binascii.crc32(data[:-4]) & 0xFFFFFFFF

print("Expected CRC32:", hex(crc_expected))
print("Calculated CRC32:", hex(crc_calc))

if crc_expected == crc_calc:
    print("CRC MATCH ✓")
else:
    print("CRC MISMATCH ✗")
