import argparse

import pytest

from tag_helpers import extract_pictures


class FakePicture:
    def __init__(self, type, mime, data):
        self.type = type
        self.mime = mime
        self.data = data


class FakeFile:
    def __init__(self, tags, pictures):
        self.tags = tags
        self.pictures = pictures


def front(data=b"front-bytes", mime="image/jpeg"):
    return FakePicture(3, mime, data)


def album_file(artist="Daft Punk", album="Discovery", pictures=None):
    return FakeFile(
        {"ARTIST": [artist], "ALBUM": [album]},
        pictures if pictures is not None else [front()],
    )


def test_slot_name_maps_known_types():
    assert extract_pictures.slot_name(front()) == "Front"
    assert extract_pictures.slot_name(FakePicture(4, "image/jpeg", b"")) == "Back"


def test_slot_name_falls_back_for_unknown_types():
    assert extract_pictures.slot_name(FakePicture(99, "image/jpeg", b"")) == "Other"


def test_extension_for_known_and_unknown_mimes():
    assert extract_pictures.extension_for(front(mime="image/png")) == ".png"
    assert extract_pictures.extension_for(front(mime="image/jpeg")) == ".jpg"
    assert extract_pictures.extension_for(front(mime="image/x-weird")) == ".x-weird"


def test_destination_name_uses_default_format():
    name = extract_pictures.destination_name(
        album_file(), front(), extract_pictures.DEFAULT_FORMAT
    )

    assert name == "Daft Punk - Discovery (Front).jpg"


def test_destination_name_defaults_missing_placeholders_to_empty():
    name = extract_pictures.destination_name(
        album_file(), front(), "{artist} - {nonexistent}"
    )

    assert name == "Daft Punk -.jpg"


def test_destination_name_sanitises_path_separators():
    music_file = album_file(artist="AC/DC")

    name = extract_pictures.destination_name(
        music_file, front(), extract_pictures.DEFAULT_FORMAT
    )

    assert "/" not in name.replace(".jpg", "")
    assert name == "AC_DC - Discovery (Front).jpg"


def test_pictures_for_handles_files_without_pictures():
    assert extract_pictures.pictures_for(FakeFile({}, [])) == []
    assert extract_pictures.pictures_for(object()) == []


def _run(tmp_path, monkeypatch, files, source=None, destination=None, fmt=None):
    """Runs extract_pictures.run against a dict of {path: FakeFile}."""
    source = source or (tmp_path / "src")
    source.mkdir(exist_ok=True)
    destination = destination or (tmp_path / "out")

    ordered = list(files.items())
    monkeypatch.setattr(
        extract_pictures, "resolve_paths", lambda *a, **k: iter([p for p, _ in ordered])
    )
    lookup = dict(ordered)
    monkeypatch.setattr(extract_pictures.tagfile, "load", lambda p: lookup[p])

    args = argparse.Namespace(
        source=str(source),
        destination=str(destination),
        extension="flac",
        format=fmt or extract_pictures.DEFAULT_FORMAT,
    )
    extract_pictures.run(args)
    return destination


def test_run_writes_a_picture(tmp_path, monkeypatch):
    path = tmp_path / "track.flac"

    destination = _run(tmp_path, monkeypatch, {path: album_file()})

    written = destination / "Daft Punk - Discovery (Front).jpg"
    assert written.read_bytes() == b"front-bytes"


def test_run_deduplicates_identical_pictures_across_files(tmp_path, monkeypatch):
    one = tmp_path / "one.flac"
    two = tmp_path / "two.flac"

    destination = _run(
        tmp_path,
        monkeypatch,
        {one: album_file(), two: album_file()},
    )

    files = list(destination.iterdir())
    assert len(files) == 1
    assert files[0].name == "Daft Punk - Discovery (Front).jpg"


def test_run_keeps_differing_pictures_sharing_a_name(tmp_path, monkeypatch):
    one = tmp_path / "one.flac"
    two = tmp_path / "two.flac"

    destination = _run(
        tmp_path,
        monkeypatch,
        {
            one: album_file(pictures=[front(data=b"aaa")]),
            two: album_file(pictures=[front(data=b"bbb")]),
        },
    )

    files = sorted(p.name for p in destination.iterdir())
    assert len(files) == 2
    assert "Daft Punk - Discovery (Front).jpg" in files
    assert any(name != "Daft Punk - Discovery (Front).jpg" for name in files)


def test_run_extracts_multiple_slots(tmp_path, monkeypatch):
    path = tmp_path / "track.flac"
    music_file = album_file(
        pictures=[front(data=b"f"), FakePicture(4, "image/png", b"b")]
    )

    destination = _run(tmp_path, monkeypatch, {path: music_file})

    names = sorted(p.name for p in destination.iterdir())
    assert names == [
        "Daft Punk - Discovery (Back).png",
        "Daft Punk - Discovery (Front).jpg",
    ]
