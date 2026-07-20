"""Repairs RIFF/truncation problems in WAVs in place by re-wrapping with ffmpeg.

``ffmpeg -c:a copy`` decodes the audio actually present and writes a fresh,
correct RIFF header. Only files that riff.inspect flags are touched, and each is
repaired atomically (temp file beside the original, then os.replace) so an error
or interrupt can never leave a half-written file.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tag_helpers import riff


def _wavs(source):
    """Yields the .wav files under source (a directory), or source itself."""
    source = Path(source)
    if source.is_dir():
        return sorted(p for p in source.glob("**/*.wav") if p.is_file())
    if source.is_file():
        return [source]
    print("source does not exist", file=sys.stderr)
    sys.exit(1)


def rewrap_in_place(src):
    """Re-wraps src atomically with ffmpeg stream-copy. Returns True on success."""
    fd, tmp_name = tempfile.mkstemp(suffix=".wav", dir=str(src.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-nostdin",
                "-i",
                str(src),
                "-c:a",
                "copy",
                "-f",
                "wav",
                str(tmp),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            logging.warning("ffmpeg failed for %s: %s", src, proc.stderr.strip()[-200:])
            return False
        os.replace(tmp, src)  # atomic on the same filesystem
        return True
    finally:
        if tmp.exists():
            tmp.unlink()


def run(args):
    dry_run = args.dry_run
    if not dry_run and shutil.which("ffmpeg") is None:
        print(
            "ffmpeg not found on PATH (install it, or pass --dry-run)",
            file=sys.stderr,
        )
        sys.exit(1)

    recovered, truncated, failed = [], [], []

    for src in _wavs(args.music_path):
        report = riff.inspect(src)
        if report is None or not report.needs_fix:
            continue

        if dry_run:
            (truncated if report.truncated else recovered).append((src, report))
            continue

        if rewrap_in_place(src):
            (truncated if report.truncated else recovered).append((src, report))
        else:
            failed.append(src)

    verb = "Would repair" if dry_run else "Repaired"
    print(
        f"{verb} (in place): {len(recovered)} recoverable, {len(truncated)} truncated\n"
    )

    print(f"== RECOVERABLE (lossless re-wrap): {len(recovered)} ==")
    for src, _report in recovered:
        print(f"  {src}")

    print(
        f"\n== TRUNCATED (salvaged, audio genuinely missing -- re-source): "
        f"{len(truncated)} =="
    )
    for src, report in truncated:
        print(
            f"  {src}\n      ~{report.missing_bytes:,} bytes / "
            f"~{report.missing_seconds:.1f}s lost"
        )

    if failed:
        print(f"\n== ffmpeg FAILED (original left untouched): {len(failed)} ==")
        for src in failed:
            print(f"  {src}")
