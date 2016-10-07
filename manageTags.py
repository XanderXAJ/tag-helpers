#!/usr/bin/env python3
# migrateAlbumArtist
# Migrates music tracks from ALBUM ARTIST to ALBUMARTIST, for wide software compatibility.
# Will also reduce ALBUMARTIST tags to just "Various" if the field contains multiple artists and one of them is either "Various" or "Various Artists"
import argparse
import taglib
import sys
from pathlib import Path

class Operation:
    """Checks the need for, and executes, operations on files"""
    def check(self, file):
        raise NotImplemented

    def execute(self, file):
        raise NotImplemented

    def safe_execute(self, file):
        if self.check(file):
            return self.execute(file)

class AlbumArtistMigrationOperation(Operation):
    """Checks and performs ALBUM ARTIST -> ALBUMARTIST migration"""
    def check(self, file):
        return 'ALBUM ARTIST' in file.tags

    def execute(self, file):
        file.tags['ALBUMARTIST'] = file.tags['ALBUM ARTIST']
        del file.tags['ALBUM ARTIST']

class AlbumArtistReductionOperation(Operation):
    """Reduces ALBUM ARTIST/ALBUMARTIST to 'Various'"""
    def check(self, file):
        for tag in ['ALBUMARTIST', 'ALBUM ARTIST']:
            if tag in file.tags:
                album_artists = list(map(str.lower, file.tags[tag]))
                if (len(album_artists) > 1
                  and ('various' in album_artists or 'various artists' in album_artists)):
                    return True
        return False

    def execute(self, file):
        file.tags['ALBUMARTIST'] = ['Various']

class RemoveFB2KPlaybacklStatisticsOperation(Operation):
    """Removes tags added by the Foobar2000 Playback Statistics plugin"""
    TAGS = ['ADDED_TIMESTAMP', 'FIRST_PLAYED_TIMESTAMP', 'LAST_PLAYED_TIMESTAMP', 'PLAY_COUNT']

    def check(self, file):
        for tag in self.TAGS:
            if tag in file.tags:
                return True
        return False

    def execute(self, file):
        for tag in self.TAGS:
            if tag in file.tags:
                del file.tags[tag]


class PrintTagsOperation(Operation):
    """Prints file tags"""
    import pprint
    pp = pprint.PrettyPrinter()

    def check(self, file):
        return True

    def execute(self, file):
        self.pp.pprint(file.tags);
        self.pp.pprint(file.unsupported)



operation_library = {
    "album_artist_migration": AlbumArtistMigrationOperation(),
    "album_artist_reduction": AlbumArtistReductionOperation(),
    "print_tags": PrintTagsOperation(),
    "remove_fb2k_playback_statistcs": RemoveFB2KPlaybacklStatisticsOperation()
}

# Yields files that require modifications
def files_requiring_operations(paths, operations):
    for path in paths:
        file = taglib.File(str(path))
        for operation in operations:
            if operation.check(file):
                yield file
                break



######

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('-o', '--operation', choices=operation_library, action='append')
parser.add_argument('music_path')
args = parser.parse_args()

# Quit immediately if no operations are to be performed
if args.operation == None:
    parser.error('No operations to perform')

operations_to_perform = [operation_library.get(x) for x in args.operation]

# Stop if music_path does not exist
music_path = Path(args.music_path)
if music_path.is_dir():
    files = files_requiring_operations(music_path.glob('**/*.flac'), operations_to_perform)
elif music_path.is_file():
    files = files_requiring_operations([music_path])
else:
    print('music_path does not exist', file=sys.stderr)
    exit(1)

# Modify files as needed
for file in files:
    print('Operating on', str(file.path))

    for operation in operations_to_perform:
        operation.safe_execute(file)

    file.save()
