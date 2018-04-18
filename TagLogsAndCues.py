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
from bs4 import UnicodeDammit

# Case-insensitive disc-matching regex
DISC_NUMBER_REGEX = re.compile(r'(?i)\Wdisc (?P<disc>[0-9]+)\W')


def find_disc_number(file):
    """Attempts to find the disc number in a file's name, returns None if none is found"""
    match = DISC_NUMBER_REGEX.search(file.stem)

    if match is not None:
        return match.group('disc')

    return None


def read_text_from_file(file, encodings):
    """Reads text from the passed file.

    Uses Unicode, Dammit to guess the file's encoding, influenced by the passed list of encodings."""
    with file.open(mode='br') as handle:
        unicode = UnicodeDammit(handle.read(), encodings)
        logging.info("%s guessed encoding: %s", file, unicode.original_encoding)
        logging.debug(unicode.unicode_markup)
        return unicode.unicode_markup


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
        logging.info('Only one file with no obvious disc number, assuming single-disc release: %s', files)
        tag_map = {'1': read_text_from_file(files[0], encoding)}

    return tag_map


def apply_disc_specific_tag(path, music_file, disc_mapping, tag):
    """Applies the appropriate disc-specific mapping to music_files's tag, if one exists.

    Returns Boolean of whether a modification was applied."""
    if 'discnumber' not in music_file:
        return False

    disc_number = music_file['discnumber'][0]
    if disc_number not in disc_mapping:
        logging.debug('Unrecognised disc %s for %s', disc_number, path)
        return False

    if tag in music_file and music_file[tag] == [disc_mapping[disc_number]]:
        logging.debug('Disc %s %s already matches, skipping %s', disc_number, tag, path)
        return False
    else:
        logging.info('Applying disc %s %s to %s', disc_number, tag, path)
        music_file[tag] = [disc_mapping[disc_number]]
        return True



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
        logging.critical("Interrupt received, stopping...")
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(1)


def main():
    """Main entrypoint"""
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--log_level', help='Set logging level', default='WARNING',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'])
    parser.add_argument('-e', '--extension', default='flac')

    # latin_1 seems to work well with UnicodeDammit and not throw encoding errors
    parser.add_argument('--cue_encoding', default=['windows-1252'])
    parser.add_argument('--log-encoding', default=[])

    parser.add_argument('music_path')
    args = parser.parse_args()

    # Set logging level
    logging.basicConfig(level=logging.getLevelName(args.log_level))

    music_path = Path(args.music_path)
    logging.info('Starting: %s', music_path)
    if not music_path.is_dir():
        logging.error('music_path is not a directory or does not exist: %s', music_path)
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
