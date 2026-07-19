# Single CLI with subcommands

## Problem

`tag-helpers` installs three separate console scripts — `TagLogsAndCues`, `manageTags`,
`printTags` — each a self-contained package with its own `main()` and `argparse` block.
The names are inconsistent in style, the shared options (`music_path`, `--extension`) are
re-declared in each tool, and behaviour that should be uniform is not: `TagLogsAndCues`
has `--log-level` and logs through `logging`, while `manageTags` and `printTags` print to
stdout and offer no logging control; `manageTags` installs a `SIGINT` handler and the
other two do not.

`TagLogsAndCues.save_atomically` already carries the comment
`# TODO: Make this in to a library function reusable by all scripts`, and `manageTags`
duplicates that same atomic-write sequence inline.

## Goal

Replace the three console scripts with one `tag-helpers` command exposing three
subcommands, and give the shared behaviour a single home.

This is a behaviour-preserving refactor apart from the deliberate changes listed under
*Breaking changes*.

## CLI surface

```
tag-helpers print    <path> [-e EXT] [--log-level LEVEL]
tag-helpers manage   <path> -o OPERATION [-o ...] [-e EXT] [--log-level LEVEL]
tag-helpers tag-logs-and-cues <path> [-e EXT] [-R] [-c ENC ...] [-l ENC ...] [--log-level LEVEL]
```

A parent parser supplies `music_path`, `-e/--extension` (default `flac`) and
`--log-level` (default `WARNING`) to every subcommand. Subcommand-specific flags stay
local: `-R/--recursive`, `-c/--cue-encoding` and `-l/--log-encoding` on
`tag-logs-and-cues`; `-o/--operation` on `manage`.

`--log-level` is lifted from `TagLogsAndCues`, keeping its existing choices
(`CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`) and `type=str.upper`. `cli.py` calls
`logging.basicConfig` once after parsing. Bringing it to the other two subcommands is a
uniformity fix, not new functionality.

### Not in this change: `--dry-run`

An earlier draft of this spec claimed `manageTags` already had `--dry-run` and that the
refactor would merely make it uniform. That was wrong — `grep -rn "dry" --include=*.py .`
matches nothing; no subcommand has ever had it.

`--dry-run` is therefore new behaviour, and is deliberately excluded so this change stays
behaviour-preserving and any post-refactor misbehaviour is unambiguously a refactor bug.
`tagfile.py` still concentrates every write in one place, so adding it afterwards is a
small isolated change.

`print` and `manage` are short verbs; `tag-logs-and-cues` deliberately is not. No concise
term covers logs and cuesheets together — "sidecars" and "rip files" were both considered
and rejected as either imprecise or requiring new vocabulary — and a shorter name such as
`tag-logs` would misrepresent the command, which writes `CUE` tags as well as `LOG` ones.
Naming it in full is preferred over naming it inaccurately.

### Breaking changes

Accepted deliberately — a clean break, no aliases or deprecation period.

- The `TagLogsAndCues`, `manageTags` and `printTags` console scripts are removed.
  Callers move to `tag-helpers tag-logs-and-cues|manage|print`.
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
  tagfile.py        # load + atomic save; the single write choke point
  print_tags.py     # run(args)
  manage_tags.py    # run(args) — discovery, dispatch to operations
  operations.py          # Operation library (manage-internal)
  tag_logs_and_cues.py   # run(args) — directory-scoped; owns encoding detection
```

`pyproject.toml` exposes a single script, `tag-helpers = "tag_helpers.cli:main"`, and
builds the single `tag_helpers` package. Each command module exposes `run(args)` taking
already-parsed arguments; `cli.py` owns all argument parsing.

Module file names keep the descriptive old names (`print_tags.py`, not `print.py`) —
the CLI is optimised for typing, the modules for reading. `print.py` would also shadow
the builtin at any import site.

### Boundaries

The commands do not share a unit of work, and this drives the module split.

`print` and `manage` are **per-file**: walk the tree, load, act, maybe save. `tag-logs-and-cues`
is **per-directory** — it assumes one release per directory, globs sibling `.log` and
`.cue` files, matches disc numbers, then writes the result into every track in that
directory. Its input is a directory's contents; its output is a batch of files.

Two unifications are therefore explicitly rejected:

- **No shared file discovery.** A common `find_files()` would have to serve both
  "walk recursively for `*.flac`" and "enumerate a release directory plus its logs and
  cues" — different return shapes and different recursion semantics. `-R` on `tag-logs-and-cues`
  does not mean what a plain recursive glob means. Each command owns its own discovery.
- **`Operation` is not extended to cover `tag-logs-and-cues`.** `Operation.check(file)` /
  `execute(file)` is per-file by construction; a directory-scoped, multi-input job would
  need context the interface does not model. `Operation` stays a `manage` concept and
  lives in `operations.py`, imported only by `manage_tags`.

What genuinely crosses the boundary is one thing: safely writing a mutagen file. Both
`manage` and `tag_logs_and_cues` perform the identical atomic-write sequence today. `tagfile.py`
owns it, and becomes the single point through which every write passes — which is what
makes a later `--dry-run` a one-place change rather than a per-command one.

`operations.py` is split out of `manage_tags.py` on size grounds (the operation classes
are most of the current 158 lines), not because anything else consumes it. The import
direction is one-way: `manage_tags → operations`.

No command module imports another. `print_tags` depends on mutagen only; `manage_tags`
on `operations` and `tagfile`; `tag_logs_and_cues` on `tagfile` and `bs4`.

## Testing

The repository currently has no tests, so the refactor carries no safety net. It adds
coverage of the logic that needs no audio fixtures — mutagen tag objects are dict-like,
so operations can be tested against plain dict stubs.

```
tests/
  test_tag_logs_and_cues.py  # find_disc_number, read_text_from_file
  test_operations.py         # each Operation's check/execute against dict stubs
  test_cli.py                # each subcommand parses to the expected args
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
