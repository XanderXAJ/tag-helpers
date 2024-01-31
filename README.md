# Tag Helpers

Python scripts to help with tagging music files.

## Installation

Clone the repo, then install using `pipx`:

```shell
pipx install ./
```

When updating (especially during development when the version number may not change), you may need to remove the existing virtualenv and then install a new one:

```shell
pipx uninstall tag-helpers
pipx install ./
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

- Handle multiple directories natively (instead of needing to be used with `find`)
- Appropriately handle UTF-16 files (or convert those files to UTF-8)
