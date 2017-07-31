"""
Tags files with logs and cuesheets that correspond to their disc.

Note: It assumes one release per directory.
"""
import argparse
import logging
import os
from pathlib import Path
import re
import shutil
import sys

from atomicwrites import atomic_write
import mutagen

DISC_NUMBER_REGEX = re.compile(r'\Wdisc (?P<disc>[0-9]+)\W')

def find_disc_number(file):
    """Attempts to find the disc number in a file's name, returns None if none is found"""
    match = DISC_NUMBER_REGEX.search(file.stem)

    if match is not None:
        return match.group('disc')

    return None

def read_text_from_file(file, encoding):
    """Reads text from file with encoding.

    Assumes Windows line endings for compatibility with Foobar2000's tag viewer."""
    with file.open(encoding=encoding, newline='\r\n') as handle:
        return handle.read()

def map_disc_numbers_to_file_contents(files, encoding):
    """Maps the disc numbers of files to their contents

    Intended for cuesheets and log files."""
    disc_numbers_to_file_contents = {}

    for file in files:
        disc_number = find_disc_number(file)
        if disc_number is not None:
            disc_numbers_to_file_contents[disc_number] = read_text_from_file(file, encoding)

    return disc_numbers_to_file_contents

def map_disc_numbers_to_values_map(files, encoding):
    """Gets a map mapping file disc numbers to appropriates values, usually file contents."""
    files = list(files)
    tag_map = map_disc_numbers_to_file_contents(files, encoding)

    if len(list(files)) == 1 and len(tag_map) == 0:
        # There is only one file and it did not feature a disc number in the name,
        # therefore assume it is disc 1 of a single-disc release
        logging.info('Only one file with no obvious disc number, assuming single-disc release')
        tag_map = {'1': read_text_from_file(files[0], encoding)}

    return tag_map

def apply_disc_specific_tag(path, music_file, disc_mapping, tag):
    """Applies the appropriate disc-specific mapping to music_files's tag, if one exists"""
    disc_number = music_file['discnumber'][0]
    if disc_number in disc_mapping:
        logging.info('Applying disc {} {} to {}'.format(disc_number, tag, path))
        music_file[tag] = [disc_mapping[disc_number]]
        return True

    return False

# TODO: Make this in to a library function reusable by all scripts
def save_atomically(path, music_file):
    """Saves changes to a mutagen music file as safely and atomically as possible"""
    try:
        # Mutagen writes directly to the file in question.  If something should go
        # wrong (e.g. power failure, shutdown), the file would be left in an undefined
        # (and probably corrupt state).  To minimise the chances of this, copy
        # contents to a temp file and swap the original and temp files as atomically
        # as possible on the platform. Atomic Writes performs the swap.
        with atomic_write(str(path), overwrite=True, mode='w+b') as temp_file:
            # Copy original file in to temp file
            with open(str(path), 'rb') as orig_file:
                shutil.copyfileobj(orig_file, temp_file)

            # Seek back to beginning of file
            temp_file.seek(0, os.SEEK_SET)

            # Write modifications to temp file
            music_file.save(temp_file)
    except (KeyboardInterrupt, SystemExit):
        logging.critical("Interrupt received, stopping...", file=sys.stderr)
        music_file.close()
        sys.exit(1)
    except BrokenPipeError:
        music_file.close()
        sys.exit(1)


def main():
    """Main entrypoint"""
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--cue_encoding', default='Windows-1252')
    parser.add_argument('--log_level', help='Set logging level', default='WARNING',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'])
    parser.add_argument('-e', '--extension', default='flac')
    parser.add_argument('--log-encoding', default='utf-16')
    parser.add_argument('music_path')
    args = parser.parse_args()

    # Set logging level
    logging.basicConfig(level=logging.getLevelName(args.log_level))

    music_path = Path(args.music_path)
    logging.info(music_path)
    if not music_path.is_dir():
        logging.error('music_path is not a directory or does not exist', file=sys.stderr)
        sys.exit(1)

    # Find LOGs
    disc_numbers_to_logs = map_disc_numbers_to_values_map(
        music_path.glob('*.log'),
        args.log_encoding
    )

    # Find CUEs
    disc_numbers_to_cues = map_disc_numbers_to_values_map(
        music_path.glob('*.cue'),
        args.cue_encoding
    )

    # Find and update music files
    for file in music_path.glob('*.{extension}'.format(extension=args.extension)):
        music_file = mutagen.File(str(file), easy=True)

        # Apply log and cue
        cue_changed = apply_disc_specific_tag(file, music_file, disc_numbers_to_cues, 'cue')
        log_changed = apply_disc_specific_tag(file, music_file, disc_numbers_to_logs, 'log')

        # Save changes
        if cue_changed or log_changed:
            save_atomically(file, music_file)

main()
