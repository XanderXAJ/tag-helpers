# Tag Helpers

Python scripts to help with tagging music files.

## Installation

Clone the repo, then install using `pipx`:

```shell
pipx install ./
```

When updating (especially during development when the version number may not change), you may need to reinstall:

```shell
pipx reinstall tag-helpers
```

## Usage

The following comamnds are installed:

- `TagLogsAndCues`: Tags music files with `*.log` and `*.cue` files in their `LOG` and `CUE` metadata fields respectively

## Development

This project is managed with Poetry:

```shell
poetry install
```

### Test installation

`poetry install` installs commands defined in [pyproject.toml](./pyproject.toml)'s `[tool.poetry.scripts]` in its virtualenv, allowing for testing of the standalone command:

```shell
poetry install && poetry run TagLogsAndCues
```

## TODO

- Skip[ directory if no cue or log files found]
- Deal with disc/track tags that also include the total, e.g. `1/1`, `01/02`, `3/10`
- Appropriately handle UTF-16 files (or convert those files to UTF-8)
