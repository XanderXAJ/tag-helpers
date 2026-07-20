import argparse
from pathlib import Path

import pytest

from tag_helpers import check, extract_pictures
from tests.wav_fixtures import make_wav


class FakePicture:
    def __init__(self, type, mime, data):
        self.type = type
        self.mime = mime
        self.data = data


class FakeFile:
    def __init__(self, pictures):
        self.tags = {}
        self.pictures = pictures


def test_check_reports_problems_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    make_wav(tmp_path / "broken.wav", samples=b"\x00" * 10, declared_data_size=1000)
    (tmp_path / "art.flac").write_bytes(b"")

    monkeypatch.setattr(extract_pictures, "FLAC_PICTURE_BLOCK_LIMIT", 100)
    big = FakePicture(3, "image/jpeg", b"x" * 200)
    monkeypatch.setattr(
        check.tagfile,
        "load_native",
        lambda p: FakeFile([big]) if Path(p).name == "art.flac" else None,
    )

    with pytest.raises(SystemExit) as exc:
        check.run(argparse.Namespace(music_path=str(tmp_path)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "broken.wav" in out
    assert "art.flac" in out


def test_check_clean_directory_does_not_exit(tmp_path, monkeypatch):
    make_wav(tmp_path / "ok.wav")
    monkeypatch.setattr(check.tagfile, "load_native", lambda p: None)

    # Must not raise SystemExit.
    check.run(argparse.Namespace(music_path=str(tmp_path)))


def test_check_survives_unreadable_files(tmp_path, monkeypatch):
    make_wav(tmp_path / "ok.wav")

    def boom(p):
        raise OSError("cannot read")

    monkeypatch.setattr(check.tagfile, "load_native", boom)

    check.run(argparse.Namespace(music_path=str(tmp_path)))
