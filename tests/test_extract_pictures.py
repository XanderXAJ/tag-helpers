import argparse
import wave

from mutagen.id3 import APIC, ID3, TALB, TPE1, TPE2
from mutagen.mp4 import MP4Cover, MP4Tags
from mutagen.wave import WAVE

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


def album_file(artist="Daft Punk", album="Discovery", albumartist=None, pictures=None):
    tags = {"ARTIST": [artist], "ALBUM": [album]}
    if albumartist is not None:
        tags["ALBUMARTIST"] = [albumartist]
    return FakeFile(tags, pictures if pictures is not None else [front()])


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


def test_destination_name_prefers_album_artist():
    music_file = album_file(artist="Thomas Bangalter", albumartist="Daft Punk")

    name = extract_pictures.destination_name(
        music_file, front(), extract_pictures.DEFAULT_FORMAT
    )

    assert name == "Daft Punk - Discovery (Front).jpg"


def test_destination_name_falls_back_to_artist_for_blank_album_artist():
    music_file = album_file(artist="Daft Punk", albumartist="")

    name = extract_pictures.destination_name(
        music_file, front(), extract_pictures.DEFAULT_FORMAT
    )

    assert name == "Daft Punk - Discovery (Front).jpg"


def test_destination_name_defaults_missing_placeholders_to_empty():
    name = extract_pictures.destination_name(
        album_file(), front(), "{artist} - {nonexistent}"
    )

    assert name == "Daft Punk -.jpg"


def test_destination_name_sanitises_path_separators():
    music_file = album_file(artist="AC/DC", album="Back in Black")

    name = extract_pictures.destination_name(
        music_file, front(), extract_pictures.DEFAULT_FORMAT
    )

    assert "/" not in name.replace(".jpg", "")
    assert name == "AC_DC - Back in Black (Front).jpg"


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
    monkeypatch.setattr(extract_pictures.tagfile, "load_native", lambda p: lookup[p])

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


class TaggedFile:
    """A file whose tags are a real mutagen tag object and which has no .pictures.

    Mirrors what mutagen returns for ID3- and MP4-based formats, where artwork
    lives in the tags rather than on a FLAC-style .pictures attribute.
    """

    def __init__(self, tags):
        self.tags = tags


def id3_file(picture_data=b"front-bytes", mime="image/jpeg"):
    tags = ID3()
    tags.add(TALB(encoding=3, text=["Discovery"]))
    tags.add(TPE1(encoding=3, text=["Thomas Bangalter"]))
    tags.add(TPE2(encoding=3, text=["Daft Punk"]))
    tags.add(APIC(encoding=0, mime=mime, type=3, desc="", data=picture_data))
    return TaggedFile(tags)


def mp4_file(picture_data=b"front-bytes", imageformat=MP4Cover.FORMAT_JPEG):
    tags = MP4Tags()
    tags["\xa9alb"] = ["Discovery"]
    tags["\xa9ART"] = ["Thomas Bangalter"]
    tags["aART"] = ["Daft Punk"]
    tags["covr"] = [MP4Cover(picture_data, imageformat=imageformat)]
    return TaggedFile(tags)


def write_wav_with_cover(path, picture_data=b"front-bytes", mime="image/jpeg"):
    """Writes a real, playable WAV file carrying an embedded ID3 cover."""
    handle = wave.open(str(path), "wb")
    handle.setnchannels(1)
    handle.setsampwidth(2)
    handle.setframerate(8000)
    handle.writeframes(b"\0\0" * 100)
    handle.close()

    music_file = WAVE(str(path))
    music_file.add_tags()
    music_file.tags.add(TALB(encoding=3, text=["Discovery"]))
    music_file.tags.add(TPE2(encoding=3, text=["Daft Punk"]))
    music_file.tags.add(APIC(encoding=0, mime=mime, type=3, desc="", data=picture_data))
    music_file.save()
    return path


def test_pictures_for_reads_id3_apic_frames():
    pictures = extract_pictures.pictures_for(id3_file())

    assert [p.data for p in pictures] == [b"front-bytes"]
    assert extract_pictures.slot_name(pictures[0]) == "Front"
    assert extract_pictures.extension_for(pictures[0]) == ".jpg"


def test_pictures_for_reads_mp4_cover_atoms():
    pictures = extract_pictures.pictures_for(mp4_file(imageformat=MP4Cover.FORMAT_PNG))

    assert [p.data for p in pictures] == [b"front-bytes"]
    assert extract_pictures.extension_for(pictures[0]) == ".png"


def test_destination_name_normalises_id3_frames():
    name = extract_pictures.destination_name(
        id3_file(),
        extract_pictures.pictures_for(id3_file())[0],
        extract_pictures.DEFAULT_FORMAT,
    )

    assert name == "Daft Punk - Discovery (Front).jpg"


def test_destination_name_normalises_mp4_atoms():
    music_file = mp4_file()

    name = extract_pictures.destination_name(
        music_file,
        extract_pictures.pictures_for(music_file)[0],
        extract_pictures.DEFAULT_FORMAT,
    )

    assert name == "Daft Punk - Discovery (Front).jpg"


def test_run_extracts_pictures_from_a_real_wav_file(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    write_wav_with_cover(source / "track.wav")
    destination = tmp_path / "out"

    extract_pictures.run(
        argparse.Namespace(
            source=str(source),
            destination=str(destination),
            extension="wav",
            format=extract_pictures.DEFAULT_FORMAT,
        )
    )

    written = destination / "Daft Punk - Discovery (Front).jpg"
    assert written.read_bytes() == b"front-bytes"


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
