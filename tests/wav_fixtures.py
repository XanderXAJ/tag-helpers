"""Builds byte-exact RIFF/WAVE files for tests, including deliberately broken ones.

declared_data_size / declared_riff_size default to the correct values; pass a
larger value to forge the "header claims more than exists" corruption.
"""

import struct
from pathlib import Path


def make_wav(
    path,
    *,
    samples=b"\x00\x00" * 100,
    declared_data_size=None,
    declared_riff_size=None,
    byte_rate=16000,
):
    path = Path(path)
    if declared_data_size is None:
        declared_data_size = len(samples)

    # fmt : audioformat, channels, samplerate, byterate, blockalign, bits
    fmt_body = struct.pack("<HHIIHH", 1, 1, 8000, byte_rate, 2, 16)
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body
    data_chunk = b"data" + struct.pack("<I", declared_data_size) + samples
    body = b"WAVE" + fmt_chunk + data_chunk

    if declared_riff_size is None:
        declared_riff_size = len(body)
    riff = b"RIFF" + struct.pack("<I", declared_riff_size) + body
    path.write_bytes(riff)
    return path
