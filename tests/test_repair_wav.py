import argparse

import pytest

from tag_helpers import repair_wav
from tests.wav_fixtures import make_wav


def test_run_rewraps_only_broken_wavs(tmp_path, monkeypatch):
    make_wav(tmp_path / "ok.wav")
    make_wav(tmp_path / "broken.wav", declared_riff_size=10_000_000)

    rewrapped = []
    monkeypatch.setattr(repair_wav.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        repair_wav, "rewrap_in_place", lambda src: rewrapped.append(src) or True
    )

    repair_wav.run(argparse.Namespace(music_path=str(tmp_path), dry_run=False))

    assert [p.name for p in rewrapped] == ["broken.wav"]


def test_dry_run_changes_nothing_and_skips_ffmpeg(tmp_path, monkeypatch, capsys):
    make_wav(tmp_path / "broken.wav", declared_riff_size=10_000_000)
    before = (tmp_path / "broken.wav").read_bytes()

    called = []
    monkeypatch.setattr(
        repair_wav, "rewrap_in_place", lambda src: called.append(src) or True
    )
    # ffmpeg absent must not matter for a dry run.
    monkeypatch.setattr(repair_wav.shutil, "which", lambda name: None)

    repair_wav.run(argparse.Namespace(music_path=str(tmp_path), dry_run=True))

    assert called == []
    assert (tmp_path / "broken.wav").read_bytes() == before
    assert "broken.wav" in capsys.readouterr().out


def test_run_errors_when_ffmpeg_missing(tmp_path, monkeypatch):
    make_wav(tmp_path / "broken.wav", declared_riff_size=10_000_000)
    monkeypatch.setattr(repair_wav.shutil, "which", lambda name: None)

    with pytest.raises(SystemExit) as exc:
        repair_wav.run(argparse.Namespace(music_path=str(tmp_path), dry_run=False))

    assert exc.value.code == 1


def test_run_accepts_a_single_file(tmp_path, monkeypatch):
    src = make_wav(tmp_path / "broken.wav", declared_riff_size=10_000_000)

    rewrapped = []
    monkeypatch.setattr(repair_wav.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        repair_wav, "rewrap_in_place", lambda s: rewrapped.append(s) or True
    )

    repair_wav.run(argparse.Namespace(music_path=str(src), dry_run=False))

    assert [p.name for p in rewrapped] == ["broken.wav"]
