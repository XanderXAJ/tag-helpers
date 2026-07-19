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
        paths = music_path.glob("**/*.{extension}".format(extension=args.extension))
    elif music_path.is_file():
        paths = [music_path]
    else:
        print("music_path does not exist", file=sys.stderr)
        sys.exit(1)

    # Modify files as needed
    for path, file in files_requiring_operations(paths, operations_to_perform):
        try:
            print("Operating on", path)

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
