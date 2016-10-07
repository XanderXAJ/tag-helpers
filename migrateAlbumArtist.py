#!/usr/bin/env python3
# migrateAlbumArtist
# Migrates music tracks from ALBUM ARTIST to ALBUMARTIST, for wide software compatibility.
# Will also reduce ALBUMARTIST tags to just "Various" if the field contains multiple artists and one of them is either "Various" or "Various Artists"
import argparse
import taglib
import sys
from pathlib import Path


# Returns whether the music file requires ALBUM ARTIST -> ALBUMARTIST migration
def needs_album_artist_migration(file):
    return 'ALBUM ARTIST' in file.tags

# Performs album artist migration
def album_artist_migration(file):
    file.tags['ALBUMARTIST'] = file.tags['ALBUM ARTIST']
    del file.tags['ALBUM ARTIST']

# Return whether the music file requires ALBUM ARTIST/ALBUMARTIST reducing to "Various"
def needs_album_artist_reduction(file):
    for tag in ['ALBUMARTIST', 'ALBUM ARTIST']:
        if tag in file.tags:
            album_artists = list(map(str.lower, file.tags[tag]))
            if (len(album_artists) > 1
              and ('various' in album_artists or 'various artists' in album_artists)):
                return True
    return False

def album_artist_reduction(file):
    file.tags['ALBUMARTIST'] = ['Various']

class Operation:
    """Checks the need for, and executes, operations on files"""
    from types import FunctionType

    def __init__(self, check, operation):
        # Requires two valid functions
        if not (isinstance(check, self.FunctionType) and isinstance(operation, self.FunctionType)):
            raise TypeError("check and operation must be functions")

        self.__check = check
        self.__operation = operation

    def check(self, file):
        return self.__check(file)

    def execute(self, file):
        return self.__operation(file)

operation_library = {
    "album_artist_migration": Operation(
        check=needs_album_artist_migration,
        operation=album_artist_migration
    ),
    "album_artist_reduction": Operation(
        check=needs_album_artist_reduction,
        operation=album_artist_reduction
    )
}

operations_to_perform = [
    operation_library.get("album_artist_migration"),
    operation_library.get("album_artist_reduction")
]

# Yields files that require modifications
def files_to_modify(paths, operations):
    for path in paths:
        file = taglib.File(str(path))
        for operation in operations:
            if operation.check(file):
                yield file
                break



######

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('music_path')
args = parser.parse_args()

# Quit immediately if no operations are to be performed
if len(operations_to_perform) <= 0:
    print('No operations to perform')
    sys.exit(0)

# Stop if music_path does not exist
music_path = Path(args.music_path)
if music_path.is_dir():
    files = files_to_modify(music_path.glob('**/*.flac'), operations_to_perform)
elif music_path.is_file():
    files = files_to_modify([music_path])
else:
    print('music_path does not exist', file=sys.stderr)
    exit(1)

# Modify files as needed
for file in files:
    print('Operating on', str(file.path))

    for operation in operations_to_perform:
        if operation.check(file):
            operation.execute(file)

    file.save()
