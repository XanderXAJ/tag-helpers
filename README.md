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

The following commands are installed:

- `TagLogsAndCues`: Tags music files with `*.log` and `*.cue` files in their `LOG` and `CUE` metadata fields respectively
- `manageTags`: Runs selected tag operations (e.g. `ALBUM ARTIST` -> `ALBUMARTIST` migration, removing playback statistics) over a file or directory
- `printTags`: Pretty prints tags for all FLAC files under a given path

## Development

```shell
uv sync
```

### Test installation

`uv sync` installs the commands defined in [pyproject.toml](./pyproject.toml)'s `[project.scripts]` into the project virtualenv, allowing the standalone commands to be tested:

```shell
uv run TagLogsAndCues
uv run manageTags
uv run printTags
```

## TODO

- Skip[ directory if no cue or log files found]
- Deal with disc/track tags that also include the total, e.g. `1/1`, `01/02`, `3/10`
- Appropriately handle UTF-16 files (or convert those files to UTF-8)
