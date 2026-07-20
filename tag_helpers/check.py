"""Read-only pre-flight check for the WAV -> FLAC conversion workflow.

Reports the two failure classes seen in the library without changing anything:
truncated/over-stated RIFF headers in WAVs, and embedded art that exceeds FLAC's
PICTURE block limit. Exits non-zero when any problem is found, so it can gate a
conversion run in a script.
"""

import logging
import sys
from pathlib import Path

from tag_helpers import riff, tagfile
from tag_helpers.extract_pictures import (
    is_oversized_for_flac,
    pictures_for,
    resolve_paths,
    slot_name,
)


def _oversized_pictures(path):
    """Yields the oversized-for-FLAC pictures in a file, tolerating unreadables."""
    try:
        music_file = tagfile.load_native(path)
    except Exception as error:  # a corrupt file must not abort the whole scan
        logging.debug("Could not read %s: %s", path, error)
        return
    if music_file is None:
        return
    for picture in pictures_for(music_file):
        if is_oversized_for_flac(picture):
            yield picture


def run(args):
    source = Path(args.music_path)

    riff_problems = []  # (path, RiffReport)
    art_problems = []  # (path, picture)

    for path in resolve_paths(source):
        if path.suffix.lower() == ".wav":
            report = riff.inspect(path)
            if report is not None and report.needs_fix:
                riff_problems.append((path, report))
        for picture in _oversized_pictures(path):
            art_problems.append((path, picture))

    print(f"== RIFF / truncation problems: {len(riff_problems)} ==")
    for path, report in riff_problems:
        detail = report.verdict
        if report.truncated:
            detail += f" (~{report.missing_bytes:,} bytes / ~{report.missing_seconds:.1f}s lost)"
        print(f"  {path}\n      {detail}")

    print(f"\n== Oversized embedded art (FLAC limit exceeded): {len(art_problems)} ==")
    for path, picture in art_problems:
        print(f"  {path}\n      {slot_name(picture)}  {len(picture.data):,} bytes")

    if riff_problems or art_problems:
        sys.exit(1)
