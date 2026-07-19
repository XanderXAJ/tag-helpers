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
