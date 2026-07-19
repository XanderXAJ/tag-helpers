# Single CLI with Subcommands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three console scripts (`TagLogsAndCues`, `manageTags`, `printTags`) with a single `tag-helpers` command exposing `print`, `manage` and `tag-logs-and-cues` subcommands.

**Architecture:** One `tag_helpers` package. `cli.py` owns all argument parsing and dispatches to a `run(args)` function per command module. `tagfile.py` holds the only genuinely shared logic — loading a mutagen file and saving it atomically — which both writing commands currently duplicate. `operations.py` holds the `Operation` library, used only by `manage_tags`. No command module imports another.

**Tech Stack:** Python 3.12+, uv, mutagen, atomicwrites, beautifulsoup4 (`UnicodeDammit`), pytest.

**Spec:** `docs/superpowers/specs/2026-07-19-single-cli-subcommands-design.md`

## Global Constraints

- Python `>=3.12` (required: `Path.walk()` and `Path.is_junction()` are 3.12+).
- This is a **behaviour-preserving refactor**. Apart from the breaking changes listed
  below, every command must behave exactly as it does today.
- **`print()` is for user-facing output; `logging` is for diagnostics.** `manage` prints
  `Operating on <path>` and `print` dumps tags to stdout unconditionally today. Do NOT
  convert these to `logging` calls — `--log-level` defaults to `WARNING`, so they would
  silently vanish. Only convert calls that are already diagnostic in nature.
- **No `--dry-run`.** It does not exist today and is explicitly out of scope.
- Breaking changes, deliberate: the three old console scripts are removed with no
  aliases; `manage` operation names become kebab-case.
- Every task ends with a passing `uv run pytest` and a commit.
- Do not fix the `README.md` TODO items (cue/log-less directories, `1/1` disc totals,
  UTF-16). Out of scope.

---

### Task 1: `tagfile.py` — the shared save, plus pytest setup

Extracts `TagLogsAndCues.save_atomically`, which already carries the comment
`# TODO: Make this in to a library function reusable by all scripts`. `manageTags`
duplicates the same sequence inline (`manageTags/__init__.py:142-151`).

**Files:**
- Create: `tag_helpers/__init__.py` (empty)
- Create: `tag_helpers/tagfile.py`
- Create: `tests/test_tagfile.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing.
- Produces: `tag_helpers.tagfile.load(path) -> mutagen.FileType` and
  `tag_helpers.tagfile.save_atomically(path, music_file) -> None`. Tasks 4 and 5 rely on
  both. `path` is a `pathlib.Path`; `save_atomically` returns `None` and calls
  `sys.exit(1)` on interrupt.

- [ ] **Step 1: Add pytest as a dev dependency**

```bash
uv add --dev pytest
```

Expected: `pyproject.toml` gains a `[dependency-groups]` block containing `pytest`, and
`uv.lock` updates.

- [ ] **Step 2: Create the package directory and empty `__init__.py`**

```bash
mkdir -p tag_helpers tests
touch tag_helpers/__init__.py
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_tagfile.py`. `save_atomically` copies the original file's bytes into a
temp file, then hands that file object to `music_file.save()`. A stub standing in for a
mutagen file lets this be tested with no audio fixtures.

```python
import pytest

from tag_helpers import tagfile


class StubMusicFile:
    """Stands in for a mutagen file. Records what it was given, writes a payload."""

    def __init__(self, payload):
        self.payload = payload
        self.saw_original = None

    def save(self, fileobj):
        fileobj.seek(0)
        self.saw_original = fileobj.read()
        fileobj.seek(0)
        fileobj.truncate()
        fileobj.write(self.payload)


def test_save_atomically_writes_payload_to_path(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")

    tagfile.save_atomically(path, StubMusicFile(b"new contents"))

    assert path.read_bytes() == b"new contents"


def test_save_atomically_gives_mutagen_the_original_contents(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")
    stub = StubMusicFile(b"new contents")

    tagfile.save_atomically(path, stub)

    assert stub.saw_original == b"original contents"


def test_save_atomically_exits_on_keyboard_interrupt(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")

    class Interrupting:
        def save(self, fileobj):
            raise KeyboardInterrupt

    with pytest.raises(SystemExit) as exc:
        tagfile.save_atomically(path, Interrupting())

    assert exc.value.code == 1
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tagfile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tag_helpers.tagfile'`

- [ ] **Step 5: Write the implementation**

Create `tag_helpers/tagfile.py`. This is a verbatim move of
`TagLogsAndCues/__init__.py:108-130`, plus a `load` helper wrapping the
`mutagen.File(str(path), easy=True)` call both commands make.

```python
"""Loading and safely saving tagged audio files.

Every write in the package goes through save_atomically.
"""
import logging
import os
import shutil
import sys

import mutagen
from atomicwrites import atomic_write


def load(path):
    """Loads a music file with mutagen's easy tag interface."""
    return mutagen.File(str(path), easy=True)


def save_atomically(path, music_file):
    """Saves changes to a mutagen music file as safely and atomically as possible"""
    try:
        # Mutagen writes directly to the file in question.  If something should go
        # wrong (e.g. power failure, shutdown), the file would be left in an undefined
        # (and probably corrupt state).  To minimise the chances of this, copy
        # contents to a temp file and swap the original and temp files as atomically
        # as possible on the platform. Atomic Writes performs the swap.
        with atomic_write(str(path), overwrite=True, mode="w+b") as temp_file:
            # Copy original file in to temp file
            with open(str(path), "rb") as orig_file:
                shutil.copyfileobj(orig_file, temp_file)

            # Seek back to beginning of file
            temp_file.seek(0, os.SEEK_SET)

            # Write modifications to temp file
            music_file.save(temp_file)
    except (KeyboardInterrupt, SystemExit):
        logging.critical("Interrupt received, stopping...")
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(1)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tagfile.py -v`
Expected: PASS, 3 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock tag_helpers/__init__.py tag_helpers/tagfile.py tests/test_tagfile.py
git commit -m "Add tag_helpers.tagfile with the shared atomic save"
```

---

### Task 2: `operations.py` — the Operation library

Moves `manageTags`' operation classes unchanged, and rekeys the library to kebab-case.

**Files:**
- Create: `tag_helpers/operations.py`
- Create: `tests/test_operations.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `tag_helpers.operations.operation_library`, a `dict[str, Operation]` keyed by
  kebab-case name. Each value has `.check(file) -> bool`, `.execute(file) -> None` and
  `.safe_execute(file) -> None`. Task 4 imports `operation_library`; Task 6 uses its keys
  as the `choices` for `-o/--operation`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_operations.py`. Mutagen's easy tags behave like a dict of
`str -> list[str]`, so plain dicts are sufficient stubs.

```python
from tag_helpers.operations import (
    AlbumArtistMigrationOperation,
    AlbumArtistReductionOperation,
    PrintTagsOperation,
    RemoveTags,
    operation_library,
)


def test_migration_checks_for_spaced_tag():
    assert AlbumArtistMigrationOperation().check({"ALBUM ARTIST": ["Bob"]}) is True
    assert AlbumArtistMigrationOperation().check({"ALBUMARTIST": ["Bob"]}) is False


def test_migration_moves_tag():
    file = {"ALBUM ARTIST": ["Bob"]}

    AlbumArtistMigrationOperation().execute(file)

    assert file == {"ALBUMARTIST": ["Bob"]}


def test_reduction_triggers_on_various_among_several():
    check = AlbumArtistReductionOperation().check
    assert check({"ALBUMARTIST": ["Various", "Bob"]}) is True
    assert check({"ALBUMARTIST": ["various artists", "Bob"]}) is True


def test_reduction_ignores_single_or_various_free_artists():
    check = AlbumArtistReductionOperation().check
    assert check({"ALBUMARTIST": ["Various"]}) is False
    assert check({"ALBUMARTIST": ["Bob", "Alice"]}) is False
    assert check({}) is False


def test_reduction_collapses_to_various():
    file = {"ALBUMARTIST": ["Various", "Bob"]}

    AlbumArtistReductionOperation().execute(file)

    assert file == {"ALBUMARTIST": ["Various"]}


def test_remove_tags_checks_and_removes_only_present_tags():
    operation = RemoveTags(tags=["RATING", "PLAY_COUNT"])
    file = {"RATING": ["5"], "TITLE": ["Song"]}

    assert operation.check(file) is True
    operation.execute(file)

    assert file == {"TITLE": ["Song"]}


def test_remove_tags_check_false_when_absent():
    assert RemoveTags(tags=["RATING"]).check({"TITLE": ["Song"]}) is False


def test_print_tags_always_checks_true_and_prints(capsys):
    class Printable(dict):
        def pprint(self):
            return "TITLE=Song"

    file = Printable()
    assert PrintTagsOperation().check(file) is True

    PrintTagsOperation().execute(file)

    assert capsys.readouterr().out == "TITLE=Song\n"


def test_safe_execute_skips_when_check_fails():
    file = {"TITLE": ["Song"]}

    RemoveTags(tags=["RATING"]).safe_execute(file)

    assert file == {"TITLE": ["Song"]}


def test_operation_library_uses_kebab_case_keys():
    assert set(operation_library) == {
        "album-artist-migration",
        "album-artist-reduction",
        "print-tags",
        "remove-fb2k-playback-statistics",
        "remove-artists-tags",
        "remove-sort-tags",
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_operations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tag_helpers.operations'`

- [ ] **Step 3: Write the implementation**

Create `tag_helpers/operations.py`. The classes are moved verbatim from
`manageTags/__init__.py:21-90`; only the `operation_library` keys change.

```python
"""Tag operations applied by the `manage` subcommand.

Each operation reports whether a file needs it (check) and applies it (execute).
"""


class Operation:
    """Represents an operation that may be executed on a file"""

    def check(self, file):
        """Checks the need for, and executes, operations on files"""
        raise NotImplementedError

    def execute(self, file):
        raise NotImplementedError

    def safe_execute(self, file):
        if self.check(file):
            return self.execute(file)


class AlbumArtistMigrationOperation(Operation):
    """Checks and performs ALBUM ARTIST -> ALBUMARTIST migration"""

    def check(self, file):
        return 'ALBUM ARTIST' in file

    def execute(self, file):
        file['ALBUMARTIST'] = file['ALBUM ARTIST']
        del file['ALBUM ARTIST']


class AlbumArtistReductionOperation(Operation):
    """Reduces ALBUM ARTIST/ALBUMARTIST to 'Various'"""

    def check(self, file):
        for tag in ['ALBUMARTIST', 'ALBUM ARTIST']:
            if tag in file:
                album_artists = list(map(str.lower, file[tag]))
                if (len(album_artists) > 1
                        and ('various' in album_artists or 'various artists' in album_artists)):
                    return True
        return False

    def execute(self, file):
        file['ALBUMARTIST'] = ['Various']


class RemoveTags(Operation):
    """Removes the specified tags"""

    def __init__(self, tags):
        self.tags = tags

    def check(self, file):
        for tag in self.tags:
            if tag in file:
                return True
        return False

    def execute(self, file):
        for tag in self.tags:
            if tag in file:
                del file[tag]


class PrintTagsOperation(Operation):
    """Prints file tags"""

    def check(self, file):
        return True

    def execute(self, file):
        print(file.pprint())


operation_library = {
    "album-artist-migration": AlbumArtistMigrationOperation(),
    "album-artist-reduction": AlbumArtistReductionOperation(),
    "print-tags": PrintTagsOperation(),
    "remove-fb2k-playback-statistics": RemoveTags(tags=['ADDED_TIMESTAMP', 'FIRST_PLAYED_TIMESTAMP', 'LAST_PLAYED_TIMESTAMP', 'PLAY_COUNT', 'RATING']),
    "remove-artists-tags": RemoveTags(tags=['ARTISTS', 'ALBUMARTISTS']),
    "remove-sort-tags": RemoveTags(tags=['ALBUMARTISTSORT', 'ALBUMSORT', 'ARTISTSORT', 'COMPOSERSORT', 'TITLESORT'])
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_operations.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add tag_helpers/operations.py tests/test_operations.py
git commit -m "Add tag_helpers.operations with kebab-case operation names"
```

---

### Task 3: `print_tags.py` — the `print` subcommand

**Files:**
- Create: `tag_helpers/print_tags.py`
- Create: `tests/test_print_tags.py`

**Interfaces:**
- Consumes: `tag_helpers.tagfile.load` (Task 1).
- Produces: `tag_helpers.print_tags.run(args) -> None` and
  `tag_helpers.print_tags.resolve_paths(music_path, extension) -> Iterable[Path]`.
  `run` reads `args.music_path` (str) and `args.extension` (str). Task 6 dispatches to
  `run`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_print_tags.py`. The path-resolution logic is the testable part;
`run` itself needs mutagen and real audio, so only its failure path is asserted.

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_print_tags.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tag_helpers.print_tags'`

- [ ] **Step 3: Write the implementation**

Create `tag_helpers/print_tags.py`. Behaviour is preserved from
`printTags/__init__.py:10-29`, including the exact stdout format and the
`music_path does not exist` stderr message. Note the original used `exit(1)`; this uses
`sys.exit(1)`, which is equivalent here and does not depend on the `site` builtin.

```python
"""Pretty prints tags for all matching music files under a given path."""
import sys
from pathlib import Path

from tag_helpers import tagfile


def resolve_paths(music_path, extension):
    """Yields the music files at music_path, which may be a file or a directory."""
    if music_path.is_dir():
        return music_path.glob('**/*.{extension}'.format(extension=extension))
    if music_path.is_file():
        return [music_path]

    print('music_path does not exist', file=sys.stderr)
    sys.exit(1)


def run(args):
    music_path = Path(args.music_path)
    paths = resolve_paths(music_path, args.extension)

    # Print tags for all files
    for path in paths:
        file = tagfile.load(path)
        print('\n\n\n', path, ': ')
        print(file.pprint())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_print_tags.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Commit**

```bash
git add tag_helpers/print_tags.py tests/test_print_tags.py
git commit -m "Add tag_helpers.print_tags for the print subcommand"
```

**Note for Task 4:** `printTags` globbed with `**/*.flac` (recursive) while its own
`--extension` did not exist — it hardcoded `.flac`. Adding `-e` here is the uniformity
change the spec calls for, and the recursive glob is preserved exactly.

---

### Task 4: `manage_tags.py` — the `manage` subcommand

**Files:**
- Create: `tag_helpers/manage_tags.py`
- Create: `tests/test_manage_tags.py`

**Interfaces:**
- Consumes: `tag_helpers.operations.operation_library` (Task 2),
  `tag_helpers.tagfile.load` and `save_atomically` (Task 1).
- Produces: `tag_helpers.manage_tags.run(args) -> None` and
  `tag_helpers.manage_tags.files_requiring_operations(paths, operations) -> Iterator[tuple[Path, file]]`.
  `run` reads `args.music_path` (str), `args.extension` (str) and `args.operation`
  (`list[str]`). Task 6 dispatches to `run`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_manage_tags.py`. `files_requiring_operations` calls `tagfile.load`,
which is monkeypatched so no audio files are needed.

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_manage_tags.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tag_helpers.manage_tags'`

- [ ] **Step 3: Write the implementation**

Create `tag_helpers/manage_tags.py`. Logic is preserved from
`manageTags/__init__.py:92-158`, with the inline atomic write replaced by
`tagfile.save_atomically`. The `Operating on <path>` line stays a `print` — it is
user-facing output, not a diagnostic.

```python
"""Runs selected tag operations over a file or directory."""
import sys
from pathlib import Path

from tag_helpers import tagfile
from tag_helpers.operations import operation_library


def files_requiring_operations(paths, operations):
    """Yields (path, file) pairs for files that require at least one operation."""
    for path in paths:
        file = tagfile.load(path)
        for operation in operations:
            if operation.check(file):
                yield (path, file)
                break


def run(args):
    operations_to_perform = [operation_library[name] for name in args.operation]

    # Stop if music_path does not exist
    music_path = Path(args.music_path)
    if music_path.is_dir():
        paths = music_path.glob('**/*.{extension}'.format(extension=args.extension))
    elif music_path.is_file():
        paths = [music_path]
    else:
        print('music_path does not exist', file=sys.stderr)
        sys.exit(1)

    # Modify files as needed
    for (path, file) in files_requiring_operations(paths, operations_to_perform):
        try:
            print('Operating on', path)

            for operation in operations_to_perform:
                operation.safe_execute(file)

            tagfile.save_atomically(path, file)
        except (KeyboardInterrupt, SystemExit):
            print("Interrupt received, stopping...", file=sys.stderr)
            file.close()
            sys.exit(1)
        except BrokenPipeError:
            file.close()
            sys.exit(1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_manage_tags.py -v`
Expected: PASS, 3 passed

- [ ] **Step 5: Commit**

```bash
git add tag_helpers/manage_tags.py tests/test_manage_tags.py
git commit -m "Add tag_helpers.manage_tags for the manage subcommand"
```

---

### Task 5: `tag_logs_and_cues.py` — the `tag-logs-and-cues` subcommand

**Files:**
- Create: `tag_helpers/tag_logs_and_cues.py`
- Create: `tests/test_tag_logs_and_cues.py`

**Interfaces:**
- Consumes: `tag_helpers.tagfile.load` and `save_atomically` (Task 1).
- Produces: `tag_helpers.tag_logs_and_cues.run(args) -> None`, plus the helpers
  `find_disc_number(file) -> int | None`, `read_text_from_file(file, encodings) -> str`,
  `map_disc_numbers_to_values_map(files, encoding) -> dict[int, str]` and
  `apply_disc_specific_tag(path, music_file, disc_mapping, tag) -> bool`. `run` reads
  `args.music_path` (str), `args.extension` (str), `args.recursive` (bool),
  `args.cue_encoding` (`list[str]`) and `args.log_encoding` (`list[str]`). Task 6
  dispatches to `run`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tag_logs_and_cues.py`.

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tag_logs_and_cues.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tag_helpers.tag_logs_and_cues'`

- [ ] **Step 3: Write the implementation**

Create `tag_helpers/tag_logs_and_cues.py`. Moved from `TagLogsAndCues/__init__.py`, with
`save_atomically` now imported from `tagfile`, and the argument parsing and
`logging.basicConfig` call removed (Task 6 owns both). The `music_path` diagnostics and
the walk are preserved exactly, including `follow_symlinks=True`.

```python
"""
Tags files with logs and cuesheets that correspond to their disc.

Note: It assumes one release per directory.
"""
import logging
import re
import sys
from pathlib import Path

from bs4 import UnicodeDammit

from tag_helpers import tagfile

# Case-insensitive disc-matching regex
DISC_NUMBER_REGEX = re.compile(r"(?i)(?:dis[ck]|cd) ?(?P<disc>[0-9]+)")


def find_disc_number(file):
    """Attempts to find the disc number in a file's name, returns None if none is found"""
    match = DISC_NUMBER_REGEX.search(file.name)

    if match is not None:
        return int(match.group("disc"))

    return None


def read_text_from_file(file, encodings):
    """Reads text from the passed file.

    Uses Unicode, Dammit to guess the file's encoding, influenced by the passed list of encodings.
    """
    with file.open(mode="br") as handle:
        unicode = UnicodeDammit(handle.read(), encodings)
        logging.debug("%s guessed encoding: %s", file, unicode.original_encoding)
        logging.debug(unicode.unicode_markup)
        return unicode.unicode_markup


def map_disc_numbers_to_file_contents(files, encoding):
    """Maps the disc numbers of files to their contents

    Intended for cuesheets and log files."""
    disc_numbers_to_file_contents = {}

    for file in files:
        disc_number = find_disc_number(file)
        logging.info("%s is for disc %s", file, disc_number)
        if disc_number is not None:
            disc_numbers_to_file_contents[disc_number] = read_text_from_file(
                file, encoding
            )

    return disc_numbers_to_file_contents


def map_disc_numbers_to_values_map(files, encoding):
    """Gets a map mapping file disc numbers to appropriates values, usually file contents."""
    files = list(files)
    tag_map = map_disc_numbers_to_file_contents(files, encoding)

    if len(list(files)) == 1 and len(tag_map) == 0:
        # There is only one file and it did not feature a disc number in the name,
        # therefore assume it is disc 1 of a single-disc release
        logging.info(
            "Only one file with no obvious disc number, assuming single-disc release: %s",
            files,
        )
        tag_map = {1: read_text_from_file(files[0], encoding)}

    return tag_map


def apply_disc_specific_tag(path, music_file, disc_mapping, tag):
    """Applies the appropriate disc-specific mapping to music_files's tag, if one exists.

    Returns Boolean of whether a modification was applied."""
    if "discnumber" not in music_file:
        return False

    disc_number = int(music_file["discnumber"][0])
    if disc_number not in disc_mapping:
        logging.info("No %s entry for disc %s, skipping %s", tag, disc_number, path)
        return False

    if tag in music_file and music_file[tag] == [disc_mapping[disc_number]]:
        logging.info(
            "Found matching %s for disc %s, skipping %s", tag, disc_number, path
        )
        return False
    else:
        logging.info(
            "Found differing %s for disc %s, applying update to %s",
            tag,
            disc_number,
            path,
        )
        music_file[tag] = [disc_mapping[disc_number]]
        return True


def process_directory(path: Path, args):
    logging.info("Processing: %s", path)

    # Find LOGs
    disc_numbers_to_logs = map_disc_numbers_to_values_map(
        path.glob("*.log"), args.log_encoding
    )

    # Find CUEs
    disc_numbers_to_cues = map_disc_numbers_to_values_map(
        path.glob("*.cue"), args.cue_encoding
    )

    # Find and update music files
    for file in path.glob("*.{extension}".format(extension=args.extension)):
        logging.debug("Working on file: %s", file)
        music_file = tagfile.load(file)

        # Apply log and cue
        cue_changed = apply_disc_specific_tag(
            file, music_file, disc_numbers_to_cues, "cue"
        )
        log_changed = apply_disc_specific_tag(
            file, music_file, disc_numbers_to_logs, "log"
        )

        # Save changes
        if cue_changed or log_changed:
            # It's probably a CD
            music_file["source"] = ["CD"]

            tagfile.save_atomically(file, music_file)


def run(args):
    music_path = Path(args.music_path)
    logging.debug("music_path: %s", music_path)
    logging.debug("music_path.exists: %s", music_path.exists())
    logging.debug("music_path.is_dir: %s", music_path.is_dir())
    logging.debug("music_path.is_junction: %s", music_path.is_junction())

    if not music_path.is_dir():
        logging.error("music_path is not a directory or does not exist: %s", music_path)
        sys.exit(1)

    for root, dirs, files in music_path.walk(follow_symlinks=True):
        process_directory(root, args)
        if not args.recursive:
            break
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tag_logs_and_cues.py -v`
Expected: PASS, 14 passed

- [ ] **Step 5: Commit**

```bash
git add tag_helpers/tag_logs_and_cues.py tests/test_tag_logs_and_cues.py
git commit -m "Add tag_helpers.tag_logs_and_cues for the tag-logs-and-cues subcommand"
```

---

### Task 6: `cli.py` — parser, dispatch and SIGINT

Wires the three command modules behind one parser. After this task the CLI works
end-to-end via `python -m tag_helpers`.

**Files:**
- Create: `tag_helpers/cli.py`
- Create: `tag_helpers/__main__.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `run(args)` from `print_tags` (Task 3), `manage_tags` (Task 4) and
  `tag_logs_and_cues` (Task 5).
- Produces: `tag_helpers.cli.build_parser() -> argparse.ArgumentParser` and
  `tag_helpers.cli.main() -> None`. Task 7 points the console script at `main`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`.

```python
import pytest

from tag_helpers import cli


def test_print_subcommand_parses_shared_options():
    args = cli.build_parser().parse_args(["print", "/music", "-e", "mp3"])

    assert args.music_path == "/music"
    assert args.extension == "mp3"
    assert args.func is not None


def test_extension_defaults_to_flac():
    args = cli.build_parser().parse_args(["print", "/music"])

    assert args.extension == "flac"


def test_log_level_available_on_every_subcommand():
    parser = cli.build_parser()

    for argv in (
        ["print", "/music"],
        ["manage", "/music", "-o", "remove-sort-tags"],
        ["tag-logs-and-cues", "/music"],
    ):
        assert parser.parse_args(argv).log_level == "WARNING"


def test_log_level_is_upper_cased():
    args = cli.build_parser().parse_args(["print", "/music", "--log-level", "debug"])

    assert args.log_level == "DEBUG"


def test_manage_accumulates_operations():
    args = cli.build_parser().parse_args(
        ["manage", "/music", "-o", "remove-sort-tags", "-o", "print-tags"]
    )

    assert args.operation == ["remove-sort-tags", "print-tags"]


def test_manage_rejects_unknown_operation():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["manage", "/music", "-o", "nonsense"])


def test_manage_requires_at_least_one_operation():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["manage", "/music"])


def test_tag_logs_and_cues_parses_its_own_options():
    args = cli.build_parser().parse_args(
        ["tag-logs-and-cues", "/music", "-R", "-l", "utf-8"]
    )

    assert args.recursive is True
    assert args.log_encoding == ["utf-8"]
    assert args.cue_encoding == ["windows-1252", "shift_jis"]


def test_tag_logs_and_cues_recursive_defaults_off():
    args = cli.build_parser().parse_args(["tag-logs-and-cues", "/music"])

    assert args.recursive is False


def test_subcommand_is_required():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_each_subcommand_dispatches_to_its_module():
    from tag_helpers import manage_tags, print_tags, tag_logs_and_cues

    parser = cli.build_parser()

    assert parser.parse_args(["print", "/m"]).func is print_tags.run
    assert (
        parser.parse_args(["manage", "/m", "-o", "print-tags"]).func is manage_tags.run
    )
    assert parser.parse_args(["tag-logs-and-cues", "/m"]).func is tag_logs_and_cues.run
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tag_helpers.cli'`

- [ ] **Step 3: Write the implementation**

Create `tag_helpers/cli.py`. `-o/--operation` is `required=True`, replacing
`manageTags`' post-parse `parser.error('No operations to perform')` — same outcome, but
argparse reports it. The SIGINT handler is lifted from `manageTags/__init__.py:15-18`
and now applies to every subcommand.

```python
"""Command line entry point for tag-helpers."""
import argparse
import logging
import signal
import sys

from tag_helpers import manage_tags, print_tags, tag_logs_and_cues
from tag_helpers.operations import operation_library


def sigint_handler(signal, frame):
    print("Interrupt received, stopping...", file=sys.stderr)
    sys.exit(1)


def build_parser():
    """Builds the argument parser for tag-helpers and its subcommands."""
    # Options every subcommand shares, supplied via a parent parser
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("music_path")
    common.add_argument("-e", "--extension", default="flac")
    common.add_argument(
        "--log-level",
        help="Set logging level",
        default="WARNING",
        type=str.upper,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
    )

    parser = argparse.ArgumentParser(
        prog="tag-helpers", description="Scripts to help with tagging music files"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    print_parser = subparsers.add_parser(
        "print",
        parents=[common],
        help="Pretty print tags for all music files under a path",
    )
    print_parser.set_defaults(func=print_tags.run)

    manage_parser = subparsers.add_parser(
        "manage",
        parents=[common],
        help="Run selected tag operations over a file or directory",
    )
    manage_parser.add_argument(
        "-o",
        "--operation",
        choices=operation_library,
        action="append",
        required=True,
    )
    manage_parser.set_defaults(func=manage_tags.run)

    logs_and_cues_parser = subparsers.add_parser(
        "tag-logs-and-cues",
        parents=[common],
        help="Tag music files with the *.log and *.cue files for their disc",
    )
    logs_and_cues_parser.add_argument("-R", "--recursive", action="store_true")
    logs_and_cues_parser.add_argument(
        "-c", "--cue-encoding", action="append", default=["windows-1252", "shift_jis"]
    )
    logs_and_cues_parser.add_argument("-l", "--log-encoding", action="append", default=[])
    logs_and_cues_parser.set_defaults(func=tag_logs_and_cues.run)

    return parser


def main():
    """Main entrypoint"""
    # Handle keyboard interrupts by default
    signal.signal(signal.SIGINT, sigint_handler)

    args = build_parser().parse_args()

    # Set logging level
    logging.basicConfig(level=logging.getLevelName(args.log_level))

    # Log configuration
    logging.info("Configuration:")
    for name, value in sorted(vars(args).items()):
        if name != "func":
            logging.info("  %s: %s", name, value)

    args.func(args)


if __name__ == "__main__":
    main()
```

Create `tag_helpers/__main__.py`:

```python
from tag_helpers.cli import main

main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS, 11 passed

- [ ] **Step 5: Verify the CLI runs end to end**

Run: `uv run python -m tag_helpers --help`
Expected: usage text listing `print`, `manage` and `tag-logs-and-cues`

Run: `uv run python -m tag_helpers manage /tmp`
Expected: exit 2, `error: the following arguments are required: -o/--operation`

- [ ] **Step 6: Commit**

```bash
git add tag_helpers/cli.py tag_helpers/__main__.py tests/test_cli.py
git commit -m "Add tag_helpers.cli wiring the three subcommands together"
```

---

### Task 7: Switch the packaging over and remove the old scripts

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Delete: `TagLogsAndCues/`, `manageTags/`, `printTags/`

**Interfaces:**
- Consumes: `tag_helpers.cli.main` (Task 6).
- Produces: the installed `tag-helpers` console script.

- [ ] **Step 1: Run the full suite to confirm a green starting point**

Run: `uv run pytest -v`
Expected: PASS, 45 passed

- [ ] **Step 2: Replace the scripts and packages in `pyproject.toml`**

Replace the `[project.scripts]` block:

```toml
[project.scripts]
tag-helpers = "tag_helpers.cli:main"
```

Replace the `[tool.hatch.build.targets.wheel]` block:

```toml
[tool.hatch.build.targets.wheel]
packages = [
	"tag_helpers",
]
```

- [ ] **Step 3: Delete the old packages**

```bash
git rm -r TagLogsAndCues manageTags printTags
```

- [ ] **Step 4: Verify the installed command works**

Run: `uv sync && uv run tag-helpers --help`
Expected: usage text listing `print`, `manage` and `tag-logs-and-cues`

Run: `uv run TagLogsAndCues`
Expected: failure — the command no longer exists

- [ ] **Step 5: Update the README**

In `README.md`, replace the *Usage* section body with:

```markdown
A single `tag-helpers` command is installed, with three subcommands:

- `tag-helpers tag-logs-and-cues`: Tags music files with `*.log` and `*.cue` files in their `LOG` and `CUE` metadata fields respectively
- `tag-helpers manage`: Runs selected tag operations (e.g. `ALBUM ARTIST` -> `ALBUMARTIST` migration, removing playback statistics) over a file or directory
- `tag-helpers print`: Pretty prints tags for all matching music files under a given path

All subcommands accept a path, `-e/--extension` (default `flac`) and `--log-level`.
```

Replace the *Test installation* section's example commands with:

```markdown
```shell
uv run tag-helpers --help
uv run tag-helpers print --help
```
```

Add a *Tests* subsection under *Development*:

```markdown
### Tests

```shell
uv run pytest
```
```

- [ ] **Step 6: Run the full suite one more time**

Run: `uv run pytest -v`
Expected: PASS, 45 passed

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Replace the three console scripts with a single tag-helpers command"
```

---

## Manual verification

The automated tests deliberately use no audio fixtures, so the end-to-end behaviour must
be checked by hand against a real library before merging. **Work on a copy** — these
commands modify files in place.

```bash
cp -r "/path/to/an/album" /tmp/verify-album
uv run tag-helpers print /tmp/verify-album
uv run tag-helpers tag-logs-and-cues /tmp/verify-album --log-level INFO
uv run tag-helpers manage /tmp/verify-album -o print-tags
uv run tag-helpers manage /tmp/verify-album -o remove-sort-tags
```

Confirm: tags print as before; `LOG`, `CUE` and `SOURCE=CD` are applied for a disc with a
matching log and cue; a second `tag-logs-and-cues` run reports the tags already match and
writes nothing; sort tags are removed. Check a multi-disc release resolves per-disc logs
and cues correctly, and that a Shift-JIS cuesheet still decodes.
