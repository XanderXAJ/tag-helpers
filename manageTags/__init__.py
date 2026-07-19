#!/usr/bin/env python3
# migrateAlbumArtist
# Migrates music tracks from ALBUM ARTIST to ALBUMARTIST, for wide software compatibility.
# Will also reduce ALBUMARTIST tags to just "Various" if the field contains multiple artists and one of them is either "Various" or "Various Artists"
import argparse
import os
import signal
import shutil
import sys
from pathlib import Path
import mutagen
from atomicwrites import atomic_write

# Handle keyboard exceptions by default
def sigint_handler(signal, frame):
    print("Interrupt received, stopping...", file=sys.stderr)
    sys.exit(1)
signal.signal(signal.SIGINT, sigint_handler)


class Operation:
    """Represents an operation that may be executed on a file"""
    def check(self, file):
        """Checks the need for, and executes, operations on files"""
        raise NotImplementedError

    def execute(self, file):
        raise NotImplementedError

    def safe_execute(self, file):
        if self.check(file):
            return self.execute(file)

class AlbumArtistMigrationOperation(Operation):
    """Checks and performs ALBUM ARTIST -> ALBUMARTIST migration"""
    def check(self, file):
        return 'ALBUM ARTIST' in file

    def execute(self, file):
        file['ALBUMARTIST'] = file['ALBUM ARTIST']
        del file['ALBUM ARTIST']

class AlbumArtistReductionOperation(Operation):
    """Reduces ALBUM ARTIST/ALBUMARTIST to 'Various'"""
    def check(self, file):
        for tag in ['ALBUMARTIST', 'ALBUM ARTIST']:
            if tag in file:
                album_artists = list(map(str.lower, file[tag]))
                if (len(album_artists) > 1
                        and ('various' in album_artists or 'various artists' in album_artists)):
                    return True
        return False

    def execute(self, file):
        file['ALBUMARTIST'] = ['Various']

class RemoveTags(Operation):
    """Removes the specified tags"""
    def __init__(self, tags):
        self.tags = tags

    def check(self, file):
        for tag in self.tags:
            if tag in file:
                return True
        return False

    def execute(self, file):
        for tag in self.tags:
            if tag in file:
                del file[tag]

class PrintTagsOperation(Operation):
    """Prints file tags"""
    def check(self, file):
        return True

    def execute(self, file):
        print(file.pprint())



operation_library = {
    "album_artist_migration": AlbumArtistMigrationOperation(),
    "album_artist_reduction": AlbumArtistReductionOperation(),
    "print_tags": PrintTagsOperation(),
    "remove_fb2k_playback_statistics": RemoveTags(tags=['ADDED_TIMESTAMP', 'FIRST_PLAYED_TIMESTAMP', 'LAST_PLAYED_TIMESTAMP', 'PLAY_COUNT', 'RATING']),
    "remove_artists_tags": RemoveTags(tags=['ARTISTS', 'ALBUMARTISTS']),
    "remove_sort_tags": RemoveTags(tags=['ALBUMARTISTSORT', 'ALBUMSORT', 'ARTISTSORT', 'COMPOSERSORT', 'TITLESORT'])
}

# Yields files that require modifications
def files_requiring_operations(paths, operations):
    for path in paths:
        file = mutagen.File(str(path), easy=True)
        for operation in operations:
            if operation.check(file):
                yield (path, file)
                break



######

def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--operation', choices=operation_library, action='append')
    parser.add_argument('-e', '--extension', default='flac')
    parser.add_argument('music_path')
    args = parser.parse_args()

    # Quit immediately if no operations are to be performed
    if args.operation == None:
        parser.error('No operations to perform')

    operations_to_perform = [operation_library.get(x) for x in args.operation]

    # Stop if music_path does not exist
    music_path = Path(args.music_path)
    if music_path.is_dir():
        files = files_requiring_operations(music_path.glob('**/*.{extension}'.format(extension=args.extension)), operations_to_perform)
    elif music_path.is_file():
        files = files_requiring_operations([music_path], operations_to_perform)
    else:
        print('music_path does not exist', file=sys.stderr)
        exit(1)

    # Modify files as needed
    for (path, file) in files:
        try:
            print('Operating on', path)

            for operation in operations_to_perform:
                operation.safe_execute(file)

            # Mutagen writes directly to the file in question.  If something should go
            # wrong (e.g. power failure, shutdown), the file would be left in an undefined
            # (and probably corrupt) state.  To minimise the chances of this, copy
            # contents to a temp file and swap the original and temp files as atomically
            # as possible on the platform. Atomic Writes performs the swap.
            with atomic_write(str(path), overwrite=True, mode='w+b') as temp_file:
                # Copy original file in to temp file
                with open(str(path), 'rb') as orig_file:
                    shutil.copyfileobj(orig_file, temp_file)

                # Seek back to beginning of file
                temp_file.seek(0, os.SEEK_SET)

                # Write modifications to temp file
                file.save(temp_file)
        except (KeyboardInterrupt, SystemExit):
            print("Interrupt received, stopping...", file=sys.stderr)
            file.close()
            sys.exit(1)
        except BrokenPipeError:
            file.close()
            sys.exit(1)
