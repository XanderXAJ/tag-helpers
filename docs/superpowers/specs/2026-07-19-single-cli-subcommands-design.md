# Single CLI with subcommands

## Problem

`tag-helpers` installs three separate console scripts — `TagLogsAndCues`, `manageTags`,
`printTags` — each a self-contained package with its own `main()` and `argparse` block.
The names are inconsistent in style, the shared options (`music_path`, `--extension`) are
re-declared in each tool, and behaviour that should be uniform is not: `manageTags`
supports `--dry-run` and installs a `SIGINT` handler, the other two do neither.

## Goal

Replace the three console scripts with one `tag-helpers` command exposing three
subcommands, and give the shared behaviour a single home.

This is a behaviour-preserving refactor apart from the deliberate changes listed under
*Breaking changes*.

## CLI surface

```
tag-helpers print    <path> [-e EXT] [--dry-run]
tag-helpers manage   <path> -o OPERATION [-o ...] [-e EXT] [--dry-run]
tag-helpers tag-logs <path> [-e EXT] [-R] [-c ENC ...] [-l ENC ...] [--dry-run]
```

A parent parser supplies `music_path`, `-e/--extension` (default `flac`) and
`--dry-run` to every subcommand. Subcommand-specific flags stay local: `-R/--recursive`,
`-c/--cue-encoding` and `-l/--log-encoding` on `tag-logs`; `-o/--operation` on `manage`.

`--dry-run` is a no-op for `print`, which is read-only. It is accepted there anyway so
the flag is uniform across subcommands.

### Breaking changes

Accepted deliberately — a clean break, no aliases or deprecation period.

- The `TagLogsAndCues`, `manageTags` and `printTags` console scripts are removed.
  Callers move to `tag-helpers tag-logs|manage|print`.
- `manage` operation names become kebab-case to match the command style:
  `album_artist_migration` → `album-artist-migration`, and likewise for
  `album-artist-reduction`, `print-tags`, `remove-fb2k-playback-statistics`,
  `remove-artists-tags`, `remove-sort-tags`.

`manage -o print-tags` is retained. It modifies a `manage` run — printing each file's
tags during processing, composable with other operations in the same pass — and is a
distinct job from the standalone `print` subcommand.

## Architecture

```
tag_helpers/
  __init__.py
  __main__.py       # from tag_helpers.cli import main; main()
  cli.py            # parser, subparsers, dispatch, SIGINT handler
  tagfile.py        # load + atomic save; the dry-run choke point
  print_tags.py     # run(args)
  manage_tags.py    # run(args) — discovery, dispatch to operations
  operations.py     # Operation library (manage-internal)
  tag_logs.py       # run(args) — directory-scoped; owns encoding detection
```

`pyproject.toml` exposes a single script, `tag-helpers = "tag_helpers.cli:main"`, and
builds the single `tag_helpers` package. Each command module exposes `run(args)` taking
already-parsed arguments; `cli.py` owns all argument parsing.

Module file names keep the descriptive old names (`print_tags.py`, not `print.py`) —
the CLI is optimised for typing, the modules for reading. `print.py` would also shadow
the builtin at any import site.

### Boundaries

The commands do not share a unit of work, and this drives the module split.

`print` and `manage` are **per-file**: walk the tree, load, act, maybe save. `tag-logs`
is **per-directory** — it assumes one release per directory, globs sibling `.log` and
`.cue` files, matches disc numbers, then writes the result into every track in that
directory. Its input is a directory's contents; its output is a batch of files.

Two unifications are therefore explicitly rejected:

- **No shared file discovery.** A common `find_files()` would have to serve both
  "walk recursively for `*.flac`" and "enumerate a release directory plus its logs and
  cues" — different return shapes and different recursion semantics. `-R` on `tag-logs`
  does not mean what a plain recursive glob means. Each command owns its own discovery.
- **`Operation` is not extended to cover `tag-logs`.** `Operation.check(file)` /
  `execute(file)` is per-file by construction; a directory-scoped, multi-input job would
  need context the interface does not model. `Operation` stays a `manage` concept and
  lives in `operations.py`, imported only by `manage_tags`.

What genuinely crosses the boundary is one thing: safely writing a mutagen file. Both
`manage` and `tag_logs` perform the identical atomic-write sequence today. `tagfile.py`
owns it, and is the single choke point where `--dry-run` is enforced — so no command can
forget to honour it.

`operations.py` is split out of `manage_tags.py` on size grounds (the operation classes
are most of the current 158 lines), not because anything else consumes it. The import
direction is one-way: `manage_tags → operations`.

No command module imports another. `print_tags` depends on mutagen only; `manage_tags`
on `operations` and `tagfile`; `tag_logs` on `tagfile` and `bs4`.

## Testing

The repository currently has no tests, so the refactor carries no safety net. It adds
coverage of the logic that needs no audio fixtures — mutagen tag objects are dict-like,
so operations can be tested against plain dict stubs.

```
tests/
  test_tag_logs.py    # find_disc_number, read_text_from_file
  test_operations.py  # each Operation's check/execute against dict stubs
  test_cli.py         # each subcommand parses to the expected args; dry-run
```

`pytest` is added as a dev dependency. End-to-end verification against a real music
library remains manual.

## Documentation

`README.md`'s *Usage* and *Test installation* sections are rewritten for the single
command. The three `uv run <script>` examples become `uv run tag-helpers <subcommand>`.

## Out of scope

- The existing `README.md` TODO items (skipping directories with no cue or log files,
  disc/track totals such as `1/1`, UTF-16 handling).
- Image and cover-art support.
- Any change to what the operations themselves do.
