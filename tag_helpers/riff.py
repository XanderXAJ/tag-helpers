"""Pure inspection of WAV RIFF headers to spot corruption before conversion.

A WAV whose RIFF header over-states the file size, or whose ``data`` chunk is cut
short, fails both conversion and tagging (a lying size hides where audio ends).
This module reads only the chunk headers -- no decoding, no ffmpeg, no writes --
and reports whether a file needs repair and whether repair would be lossless.
"""

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RiffReport:
    byte_rate: int
    data_declared: int
    data_available: int
    riff_declared_total: int
    actual: int

    @property
    def truncated(self):
        """True when the data chunk claims more bytes than actually follow it."""
        return self.data_available < self.data_declared

    @property
    def header_inflated(self):
        """True when the RIFF header implies a larger file than exists on disk."""
        return self.riff_declared_total > self.actual

    @property
    def needs_fix(self):
        return self.truncated or self.header_inflated

    @property
    def verdict(self):
        # Truncated means audio is genuinely missing; otherwise the header merely
        # lied and a re-wrap is lossless.
        return "TRUNCATED" if self.truncated else "RECOVERABLE"

    @property
    def missing_bytes(self):
        return max(0, self.data_declared - self.data_available)

    @property
    def missing_seconds(self):
        return self.missing_bytes / self.byte_rate if self.byte_rate else 0.0


def inspect(path):
    """Returns a RiffReport for a plain RIFF/WAVE file, or None if not applicable.

    None covers non-RIFF files, non-WAVE RIFFs, RF64, and files with no data
    chunk -- nothing this module should reason about or touch.
    """
    path = Path(path)
    actual = path.stat().st_size
    with path.open("rb") as f:
        header = f.read(12)
        if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
            return None
        riff_size = struct.unpack("<I", header[4:8])[0]
        riff_declared_total = riff_size + 8

        byte_rate = 0
        data_declared = None
        data_available = None
        offset = 12
        while offset + 8 <= actual:
            f.seek(offset)
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            cid = chunk_header[0:4]
            csize = struct.unpack("<I", chunk_header[4:8])[0]
            data_start = offset + 8

            if cid == b"fmt " and csize >= 16:
                fmt = f.read(16)
                byte_rate = struct.unpack("<I", fmt[8:12])[0]
            elif cid == b"data":
                data_declared = csize
                data_available = actual - data_start
                break  # the tail is what matters; stop walking here

            offset = data_start + csize + (csize & 1)  # chunks are word-aligned

    if data_declared is None:
        return None
    return RiffReport(
        byte_rate, data_declared, data_available, riff_declared_total, actual
    )
