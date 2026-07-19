import argparse

import pytest

from tag_helpers import manage_tags
from tag_helpers.operations import RemoveTags


def test_files_requiring_operations_yields_only_matching_files(tmp_path, monkeypatch):
    needs = tmp_path / "needs.flac"
    clean = tmp_path / "clean.flac"
    needs.touch()
    clean.touch()

    tags = {needs: {"RATING": ["5"]}, clean: {"TITLE": ["Song"]}}
    monkeypatch.setattr(manage_tags.tagfile, "load", lambda path: tags[path])

    results = list(
        manage_tags.files_requiring_operations(
            [needs, clean], [RemoveTags(tags=["RATING"])]
        )
    )

    assert [path for path, _ in results] == [needs]


def test_files_requiring_operations_yields_once_for_multiple_matches(tmp_path, monkeypatch):
    path = tmp_path / "track.flac"
    path.touch()
    monkeypatch.setattr(
        manage_tags.tagfile, "load", lambda _: {"RATING": ["5"], "ARTISTS": ["Bob"]}
    )

    results = list(
        manage_tags.files_requiring_operations(
            [path], [RemoveTags(tags=["RATING"]), RemoveTags(tags=["ARTISTS"])]
        )
    )

    assert len(results) == 1


def test_run_applies_operations_and_saves(tmp_path, monkeypatch, capsys):
    path = tmp_path / "track.flac"
    path.touch()
    music_file = {"ALBUMSORT": ["Album"], "TITLE": ["Song"]}
    saved = []
    monkeypatch.setattr(manage_tags.tagfile, "load", lambda _: music_file)
    monkeypatch.setattr(
        manage_tags.tagfile, "save_atomically", lambda p, f: saved.append(p)
    )

    args = argparse.Namespace(
        music_path=str(tmp_path), extension="flac", operation=["remove-sort-tags"]
    )
    manage_tags.run(args)

    assert music_file == {"TITLE": ["Song"]}
    assert saved == [path]
    assert "Operating on" in capsys.readouterr().out


def test_run_leaves_untouched_files_alone(tmp_path, monkeypatch):
    (tmp_path / "track.flac").touch()
    saved = []
    monkeypatch.setattr(manage_tags.tagfile, "load", lambda _: {"TITLE": ["Song"]})
    monkeypatch.setattr(
        manage_tags.tagfile, "save_atomically", lambda p, f: saved.append(p)
    )

    args = argparse.Namespace(
        music_path=str(tmp_path), extension="flac", operation=["remove-sort-tags"]
    )
    manage_tags.run(args)

    assert saved == []


def test_run_accepts_a_single_file(tmp_path, monkeypatch):
    path = tmp_path / "track.flac"
    path.touch()
    saved = []
    monkeypatch.setattr(manage_tags.tagfile, "load", lambda _: {"ALBUMSORT": ["A"]})
    monkeypatch.setattr(
        manage_tags.tagfile, "save_atomically", lambda p, f: saved.append(p)
    )

    args = argparse.Namespace(
        music_path=str(path), extension="flac", operation=["remove-sort-tags"]
    )
    manage_tags.run(args)

    assert saved == [path]


def test_run_exits_when_path_missing(tmp_path, capsys):
    args = argparse.Namespace(
        music_path=str(tmp_path / "absent"),
        extension="flac",
        operation=["remove-sort-tags"],
    )

    with pytest.raises(SystemExit) as exc:
        manage_tags.run(args)

    assert exc.value.code == 1
    assert "music_path does not exist" in capsys.readouterr().err
