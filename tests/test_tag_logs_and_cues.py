import argparse
from pathlib import Path

import pytest

from tag_helpers import tag_logs_and_cues as tlc


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Album Disc 2.log", 2),
        ("Album Disk 3.log", 3),
        ("Album CD 4.cue", 4),
        ("Album cd5.cue", 5),
        ("Album DISC10.log", 10),
        ("Album.log", None),
    ],
)
def test_find_disc_number(name, expected):
    assert tlc.find_disc_number(Path(name)) == expected


def test_read_text_from_file_uses_supplied_encodings(tmp_path):
    path = tmp_path / "disc 1.cue"
    path.write_bytes("トラック".encode("shift_jis"))

    assert tlc.read_text_from_file(path, ["shift_jis"]) == "トラック"


@pytest.mark.parametrize(
    "encoding",
    ["utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-8-sig"],
)
def test_read_text_from_file_honours_byte_order_marks(tmp_path, encoding):
    """A BOM is authoritative and must beat the supplied fallback encodings."""
    text = 'PERFORMER "Björk"\nTITLE "Homogenic"\n'
    path = tmp_path / "disc 1.cue"
    path.write_bytes(text.encode(encoding))

    assert tlc.read_text_from_file(path, ["windows-1252", "shift_jis"]) == text


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_read_text_from_file_detects_utf_16_without_a_bom(tmp_path, encoding):
    text = 'PERFORMER "Björk"\nTITLE "Homogenic"\n'
    path = tmp_path / "disc 1.cue"
    path.write_bytes(text.encode(encoding))

    assert tlc.read_text_from_file(path, ["windows-1252", "shift_jis"]) == text


def test_read_text_from_file_prefers_utf_8_over_the_fallbacks(tmp_path):
    """windows-1252 decodes any bytes, so it must never pre-empt valid UTF-8."""
    text = 'PERFORMER "Björk"\n'
    path = tmp_path / "disc 1.cue"
    path.write_bytes(text.encode("utf-8"))

    assert tlc.read_text_from_file(path, ["windows-1252", "shift_jis"]) == text


def test_read_text_from_file_uses_fallbacks_in_order(tmp_path):
    text = "トラック"
    path = tmp_path / "disc 1.cue"
    path.write_bytes(text.encode("shift_jis"))

    assert tlc.read_text_from_file(path, ["shift_jis", "windows-1252"]) == text


def test_read_text_from_file_falls_back_to_windows_1252(tmp_path):
    """Undecodable-elsewhere bytes still yield text rather than raising."""
    path = tmp_path / "disc 1.cue"
    path.write_bytes(b"caf\xe9")

    assert tlc.read_text_from_file(path, []) == "café"


def test_read_text_from_file_skips_unknown_encoding_names(tmp_path):
    """A typo in --cue-encoding should not be fatal; later candidates still apply."""
    path = tmp_path / "disc 1.cue"
    path.write_bytes("トラック".encode("shift_jis"))

    assert tlc.read_text_from_file(path, ["not-an-encoding", "shift_jis"]) == "トラック"


def test_read_text_from_file_leaves_the_file_untouched(tmp_path):
    path = tmp_path / "disc 1.cue"
    raw = 'TITLE "Homogenic"\n'.encode("utf-16")
    path.write_bytes(raw)

    tlc.read_text_from_file(path, ["windows-1252"])

    assert path.read_bytes() == raw


def test_map_disc_numbers_maps_by_number(tmp_path):
    (tmp_path / "rip disc 1.log").write_text("first")
    (tmp_path / "rip disc 2.log").write_text("second")

    mapping = tlc.map_disc_numbers_to_values_map(tmp_path.glob("*.log"), ["utf-8"])

    assert mapping == {1: "first", 2: "second"}


def test_map_disc_numbers_assumes_disc_one_for_lone_unnumbered_file(tmp_path):
    (tmp_path / "rip.log").write_text("only")

    mapping = tlc.map_disc_numbers_to_values_map(tmp_path.glob("*.log"), ["utf-8"])

    assert mapping == {1: "only"}


def test_apply_disc_specific_tag_sets_missing_tag():
    music_file = {"discnumber": ["1"]}

    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), music_file, {1: "contents"}, "log"
    )

    assert changed is True
    assert music_file["log"] == ["contents"]


def test_apply_disc_specific_tag_skips_when_already_matching():
    music_file = {"discnumber": ["1"], "log": ["contents"]}

    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), music_file, {1: "contents"}, "log"
    )

    assert changed is False


def test_apply_disc_specific_tag_skips_without_discnumber():
    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), {}, {1: "contents"}, "log"
    )

    assert changed is False


def test_apply_disc_specific_tag_reads_a_combined_discnumber():
    """Files tagged `2/3` should still be matched to disc 2 rather than blowing up."""
    music_file = {"discnumber": ["2/3"]}

    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), music_file, {2: "contents"}, "log"
    )

    assert changed is True
    assert music_file["log"] == ["contents"]


def test_apply_disc_specific_tag_skips_an_unparseable_discnumber():
    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), {"discnumber": ["one"]}, {1: "contents"}, "log"
    )

    assert changed is False


def test_apply_disc_specific_tag_skips_when_no_entry_for_disc():
    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), {"discnumber": ["2"]}, {1: "contents"}, "log"
    )

    assert changed is False


def make_release(directory, *, log="log contents", cue="cue contents"):
    """Creates a single-disc release directory with one log, one cue and one track."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "rip.log").write_text(log)
    (directory / "rip.cue").write_text(cue)
    (directory / "track.flac").touch()


def stub_tagfile(monkeypatch, music_file):
    """Points tagfile.load at music_file and records what gets saved."""
    saved = []
    monkeypatch.setattr(tlc.tagfile, "load", lambda path: music_file)
    monkeypatch.setattr(
        tlc.tagfile, "save_atomically", lambda path, file: saved.append(path)
    )
    return saved


def directory_args(**overrides):
    defaults = dict(
        extension="flac",
        recursive=False,
        cue_encoding=["utf-8"],
        log_encoding=["utf-8"],
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_process_directory_applies_log_and_cue_and_marks_source_as_cd(
    tmp_path, monkeypatch
):
    """The 'It's probably a CD' comment: a applied log or cue implies SOURCE=CD."""
    make_release(tmp_path)
    music_file = {"discnumber": ["1"]}
    saved = stub_tagfile(monkeypatch, music_file)

    tlc.process_directory(tmp_path, directory_args())

    assert music_file["log"] == ["log contents"]
    assert music_file["cue"] == ["cue contents"]
    assert music_file["source"] == ["CD"]
    assert saved == [tmp_path / "track.flac"]


def test_process_directory_does_not_save_when_tags_already_match(tmp_path, monkeypatch):
    make_release(tmp_path)
    music_file = {
        "discnumber": ["1"],
        "log": ["log contents"],
        "cue": ["cue contents"],
    }
    saved = stub_tagfile(monkeypatch, music_file)

    tlc.process_directory(tmp_path, directory_args())

    assert saved == []
    assert "source" not in music_file


def test_process_directory_ignores_files_of_other_extensions(tmp_path, monkeypatch):
    make_release(tmp_path)
    (tmp_path / "track.mp3").touch()
    saved = stub_tagfile(monkeypatch, {"discnumber": ["1"]})

    tlc.process_directory(tmp_path, directory_args(extension="mp3"))

    assert saved == [tmp_path / "track.mp3"]


def test_process_directory_matches_logs_and_cues_per_disc(tmp_path, monkeypatch):
    """One release per directory, but multiple discs within it."""
    (tmp_path / "rip disc 1.log").write_text("first log")
    (tmp_path / "rip disc 2.log").write_text("second log")
    (tmp_path / "rip disc 1.cue").write_text("first cue")
    (tmp_path / "rip disc 2.cue").write_text("second cue")
    (tmp_path / "track.flac").touch()

    music_file = {"discnumber": ["2"]}
    stub_tagfile(monkeypatch, music_file)

    tlc.process_directory(tmp_path, directory_args())

    assert music_file["log"] == ["second log"]
    assert music_file["cue"] == ["second cue"]


def test_process_directory_skips_directories_without_logs_or_cues(
    tmp_path, monkeypatch
):
    """Without a log or a cue there is nothing to apply, so don't read the music files."""
    (tmp_path / "track.flac").touch()
    loaded = []
    monkeypatch.setattr(tlc.tagfile, "load", lambda path: loaded.append(path))

    tlc.process_directory(tmp_path, directory_args())

    assert loaded == []


def test_run_processes_only_the_top_directory_by_default(tmp_path, monkeypatch):
    (tmp_path / "nested").mkdir()
    visited = []
    monkeypatch.setattr(
        tlc, "process_directory", lambda path, args: visited.append(path)
    )

    tlc.run(directory_args(music_path=str(tmp_path)))

    assert visited == [tmp_path]


def test_run_recurses_when_asked(tmp_path, monkeypatch):
    (tmp_path / "nested").mkdir()
    visited = []
    monkeypatch.setattr(
        tlc, "process_directory", lambda path, args: visited.append(path)
    )

    tlc.run(directory_args(music_path=str(tmp_path), recursive=True))

    assert sorted(visited) == [tmp_path, tmp_path / "nested"]


def test_run_exits_when_path_is_not_a_directory(tmp_path):
    args = argparse.Namespace(
        music_path=str(tmp_path / "absent"),
        extension="flac",
        recursive=False,
        cue_encoding=["windows-1252"],
        log_encoding=[],
    )

    with pytest.raises(SystemExit) as exc:
        tlc.run(args)

    assert exc.value.code == 1
