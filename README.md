# Tag Helpers

Python scripts to help with tagging music files.

## Installation

Clone the repo, then install using `pipx`:

```shell
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

### Development Usage

Use `poetry run` to run the command you want.

## TODO

- Handle multiple directories natively (instead of needing to be used with `find`)
- Appropriately handle UTF-16 files (or convert those files to UTF-8)
