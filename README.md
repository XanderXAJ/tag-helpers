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
uv tool install ./
```

To update:

```shell
uv tool upgrade tag-helpers
```

During development the version number may not change, in which case force a reinstall:

```shell
uv tool install --reinstall ./
```

## Usage

A single `tag-helpers` command is installed, with four subcommands:

- `tag-helpers tag-logs-and-cues`: Tags music files with `*.log` and `*.cue` files in their `LOG` and `CUE` metadata fields respectively
- `tag-helpers manage`: Runs selected tag operations (e.g. `ALBUM ARTIST` -> `ALBUMARTIST` migration, removing playback statistics) over a file or directory
- `tag-helpers print`: Pretty prints tags for all matching music files under a given path
- `tag-helpers extract-pictures`: Extracts embedded pictures from files (recursing a source directory) into a destination directory

All subcommands accept `-e/--extension` (default `flac`) and `--log-level`. Every
subcommand except `extract-pictures` also takes a music path; `extract-pictures`
takes a `source` and a `destination` instead.

### Extracting pictures

`tag-helpers extract-pictures SOURCE DESTINATION` recurses `SOURCE` for all
matching files and writes each embedded picture into `DESTINATION`. The
destination file name is built from `-f/--format`, whose default is
`{artist} - {album} ({slot})`, producing names such as
`Daft Punk - Discovery (Front).jpg`.

The format string supports:

- Any tag as a placeholder, e.g. `{artist}`, `{album}`, `{albumartist}` (tag
  names are matched case-insensitively; unknown placeholders resolve to empty)
- `{slot}`: the picture's slot (`Front`, `Back`, `Leaflet`, ...)

The file extension is chosen automatically from the picture's MIME type.
Pictures whose formatted name and contents match one already written are
skipped, so artwork shared across an album's tracks -- or across albums -- is
only extracted once.

If you previously installed the separate `TagLogsAndCues`, `manageTags` and `printTags`
commands, reinstall to replace them:

```shell
uv tool install --reinstall git+https://github.com/XanderXAJ/tag-helpers
```

## Development

```shell
uv sync
```

### Test installation

`uv sync` installs the commands defined in [pyproject.toml](./pyproject.toml)'s `[project.scripts]` into the project virtualenv, allowing the standalone commands to be tested:

```shell
uv run tag-helpers --help
uv run tag-helpers print --help
```

Note that `uv run <command>` falls back to any command of that name on your `PATH`, so a
previously installed copy can mask the project virtualenv's. `which -a tag-helpers` will
show which is being picked up.

### Tests

```shell
uv run pytest
```

## TODO

- Skip[ directory if no cue or log files found]
- Deal with disc/track tags that also include the total, e.g. `1/1`, `01/02`, `3/10`
- Appropriately handle UTF-16 files (or convert those files to UTF-8)
