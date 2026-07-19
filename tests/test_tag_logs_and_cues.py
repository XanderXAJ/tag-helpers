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


def test_apply_disc_specific_tag_skips_when_no_entry_for_disc():
    changed = tlc.apply_disc_specific_tag(
        Path("track.flac"), {"discnumber": ["2"]}, {1: "contents"}, "log"
    )

    assert changed is False


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
