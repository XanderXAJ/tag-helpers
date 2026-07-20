# Tag Helpers

Python scripts to help with tagging music files.

## Installation

This project is managed with [`uv`](https://docs.astral.sh/uv/), which bootstraps its own Python -- no existing Python installation is required.

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install git+https://github.com/XanderXAJ/tag-helpers
```

To install from a local clone instead:

```shell
mise run install
```

To update:

```shell
uv tool upgrade tag-helpers
```

## Usage

A single `tag-helpers` command is installed, with the following subcommands:

- `tag-helpers tag-logs-and-cues`: Tags music files with `*.log` and `*.cue` files in their `LOG` and `CUE` metadata fields respectively
- `tag-helpers manage`: Runs selected tag operations (e.g. `ALBUM ARTIST` -> `ALBUMARTIST` migration, removing playback statistics) over a file or directory
- `tag-helpers print`: Pretty prints tags for all matching music files under a given path
- `tag-helpers extract-pictures`: Extracts embedded pictures from files (recursing a source directory) into a destination directory

All subcommands accept `-e/--extension` (default `flac`) and `--log-level`. Every
subcommand except `extract-pictures` also takes a music path; `extract-pictures`
takes a `source` and a `destination` instead.

### Text encodings

Log and cue files carry no reliable declaration of their own encoding, and rippers
have historically written them in whatever the ripping machine's locale happened to
be. `tag-helpers tag-logs-and-cues` therefore tries a fixed sequence of encodings and
uses the first that decodes cleanly:

1. A byte order mark, if present -- authoritative, and wins outright (UTF-8, UTF-16
   and UTF-32 are all recognised; the mark itself is consumed rather than left in the
   text)
2. UTF-16 without a byte order mark, detected from its interleaved NUL bytes
3. UTF-8, strictly
4. Your `-c/--cue-encoding` and `-l/--log-encoding` values, in the order given
5. `windows-1252`, as a last resort

Steps 1--3 are self-validating: text that decodes as UTF-8 or carries a BOM is
essentially never that sequence by accident, so these are safe to try first. The
single-byte encodings in steps 4--5 are not -- `windows-1252` in particular decodes
*any* byte sequence without complaint, which is why it can only ever come last.
Anything it mis-decodes yields mojibake (`BjÃ¶rk` for `Björk`) rather than an error.

Both flags may be repeated to try several encodings in turn:

```shell
tag-helpers tag-logs-and-cues -c shift_jis -c euc-jp /path/to/music
```

Any [encoding Python knows](https://docs.python.org/3/library/codecs.html#standard-encodings)
is accepted; unrecognised names are skipped rather than treated as fatal.

`--cue-encoding` defaults to `windows-1252` then `shift_jis`, reflecting how commonly
cuesheets come from Western and Japanese rips. `--log-encoding` has no defaults, as
the steps above already cover the UTF-8 and UTF-16 that modern rippers emit.

Note that these flags *add to* the defaults rather than replace them, so
`-c cp1251` still tries `windows-1252` before `cp1251`. Since `windows-1252` never
fails, passing another single-byte encoding this way will not have the effect you
want; the BOM and UTF-8 steps are unaffected.

Files are only ever read. Nothing is rewritten or converted on disk, whatever
encoding it turns out to be in.

### Extracting pictures

`tag-helpers extract-pictures SOURCE DESTINATION` recurses `SOURCE` for all
matching files and writes each embedded picture into `DESTINATION`. The
destination file name is built from `-f/--format`, whose default is
`{albumartist} - {album} ({slot})`, producing names such as
`Daft Punk - Discovery (Front).jpg`.

The format string supports:

- Any tag as a placeholder, e.g. `{artist}`, `{album}`, `{albumartist}` (tag
  names are matched case-insensitively; unknown placeholders resolve to empty)
- `{albumartist}`: falls back to `{artist}` when the file has no album artist,
  so a compilation's shared artwork is written once rather than once per track
  artist
- `{slot}`: the picture's slot (`Front`, `Back`, `Leaflet`, ...)

Artwork is read from FLAC pictures, ID3 `APIC` frames (MP3, WAV, AIFF) and MP4
`covr` atoms. The file extension is chosen automatically from the picture's MIME
type.
Pictures whose formatted name and contents match one already written are
skipped, so artwork shared across an album's tracks -- or across albums -- is
only extracted once.

If you previously installed the separate `TagLogsAndCues`, `manageTags` and `printTags`
commands, reinstall to replace them:

```shell
uv tool install --reinstall git+https://github.com/XanderXAJ/tag-helpers
```

## Development

Tooling and tasks are defined in [mise.toml](./mise.toml); `mise tasks` lists them.

```shell
mise run setup
```

### Running the CLI without installing

`mise run setup` puts the commands defined in [pyproject.toml](./pyproject.toml)'s `[project.scripts]` into the project virtualenv, so they can be run without installing the tool:

```shell
uv run tag-helpers --help
uv run tag-helpers print --help
```

Note that `uv run <command>` falls back to any command of that name on your `PATH`, so a
previously installed copy can mask the project virtualenv's. `which -a tag-helpers` will
show which is being picked up.

### Tests

```shell
mise run test
```
