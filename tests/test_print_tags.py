import argparse

import pytest

from tag_helpers import print_tags


def test_resolve_paths_globs_a_directory(tmp_path):
    (tmp_path / "one.flac").touch()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "two.flac").touch()
    (tmp_path / "cover.jpg").touch()

    found = sorted(p.name for p in print_tags.resolve_paths(tmp_path, "flac"))

    assert found == ["one.flac", "two.flac"]


def test_resolve_paths_accepts_a_single_file(tmp_path):
    path = tmp_path / "one.flac"
    path.touch()

    assert list(print_tags.resolve_paths(path, "flac")) == [path]


def test_resolve_paths_honours_extension(tmp_path):
    (tmp_path / "one.flac").touch()
    (tmp_path / "two.mp3").touch()

    found = [p.name for p in print_tags.resolve_paths(tmp_path, "mp3")]

    assert found == ["two.mp3"]


def test_run_exits_when_path_missing(tmp_path, capsys):
    args = argparse.Namespace(
        music_path=str(tmp_path / "absent"), extension="flac"
    )

    with pytest.raises(SystemExit) as exc:
        print_tags.run(args)

    assert exc.value.code == 1
    assert "music_path does not exist" in capsys.readouterr().err
