#!/usr/bin/env python3
# migrateAlbumArtist
# Migrates music tracks from ALBUM ARTIST to ALBUMARTIST, for wide software compatibility.
# Will also reduce ALBUMARTIST tags to just "Various" if the field contains multiple artists and one of them is either "Various" or "Various Artists"
import argparse
import taglib
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('music_path')
args = parser.parse_args()

# Returns whether the music file requires ALBUM ARTIST -> ALBUMARTIST migration
def needs_album_artist_migration(file):
    return 'ALBUM ARTIST' in file.tags

# Return whether the music file requires
def needs_album_artist_reduction(file):
    for tag in ['ALBUMARTIST', 'ALBUM ARTIST']:
        if tag in file.tags:
            album_artists = list(map(str.lower, file.tags[tag]))
            if (len(album_artists) > 1
              and ('various' in album_artists or 'various artists' in album_artists)):
                return True
    return False

# Yields files that require modifications
def files_to_modify(paths):
    for path in paths:
        file = taglib.File(str(path))
        if needs_album_artist_migration(file) or needs_album_artist_reduction(file):
            yield file

# Stop if music_path does not exist
music_path = Path(args.music_path)
if not music_path.exists():
    print('music_path does not exist', file=sys.stderr)
    exit(1)

# Modify files as needed
for file in files_to_modify(music_path.glob('**/*.flac')):
    print('Migrating', str(file.path))

    if needs_album_artist_migration(file):
        file.tags['ALBUMARTIST'] = file.tags['ALBUM ARTIST']
        del file.tags['ALBUM ARTIST']

    if needs_album_artist_reduction(file):
        file.tags['ALBUMARTIST'] = ['Various']

    file.save()
