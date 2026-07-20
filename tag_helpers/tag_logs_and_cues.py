"""
Tags files with logs and cuesheets that correspond to their disc.

Note: It assumes one release per directory.
"""

import logging
import re
import sys
from pathlib import Path

from bs4 import UnicodeDammit

from tag_helpers import tagfile

# Case-insensitive disc-matching regex
DISC_NUMBER_REGEX = re.compile(r"(?i)(?:dis[ck]|cd) ?(?P<disc>[0-9]+)")


def find_disc_number(file):
    """Attempts to find the disc number in a file's name, returns None if none is found"""
    match = DISC_NUMBER_REGEX.search(file.name)

    if match is not None:
        return int(match.group("disc"))

    return None


def read_text_from_file(file, encodings):
    """Reads text from the passed file.

    Uses Unicode, Dammit to guess the file's encoding, influenced by the passed list of encodings.
    """
    with file.open(mode="br") as handle:
        unicode = UnicodeDammit(handle.read(), encodings)
        logging.debug("%s guessed encoding: %s", file, unicode.original_encoding)
        logging.debug(unicode.unicode_markup)
        return unicode.unicode_markup


def map_disc_numbers_to_file_contents(files, encoding):
    """Maps the disc numbers of files to their contents

    Intended for cuesheets and log files."""
    disc_numbers_to_file_contents = {}

    for file in files:
        disc_number = find_disc_number(file)
        logging.info("%s is for disc %s", file, disc_number)
        if disc_number is not None:
            disc_numbers_to_file_contents[disc_number] = read_text_from_file(
                file, encoding
            )

    return disc_numbers_to_file_contents


def map_disc_numbers_to_values_map(files, encoding):
    """Gets a map mapping file disc numbers to appropriates values, usually file contents."""
    files = list(files)
    tag_map = map_disc_numbers_to_file_contents(files, encoding)

    if len(list(files)) == 1 and len(tag_map) == 0:
        # There is only one file and it did not feature a disc number in the name,
        # therefore assume it is disc 1 of a single-disc release
        logging.info(
            "Only one file with no obvious disc number, assuming single-disc release: %s",
            files,
        )
        tag_map = {1: read_text_from_file(files[0], encoding)}

    return tag_map


def apply_disc_specific_tag(path, music_file, disc_mapping, tag):
    """Applies the appropriate disc-specific mapping to music_files's tag, if one exists.

    Returns Boolean of whether a modification was applied."""
    if "discnumber" not in music_file:
        return False

    disc_number = int(music_file["discnumber"][0])
    if disc_number not in disc_mapping:
        logging.info("No %s entry for disc %s, skipping %s", tag, disc_number, path)
        return False

    if tag in music_file and music_file[tag] == [disc_mapping[disc_number]]:
        logging.info(
            "Found matching %s for disc %s, skipping %s", tag, disc_number, path
        )
        return False
    else:
        logging.info(
            "Found differing %s for disc %s, applying update to %s",
            tag,
            disc_number,
            path,
        )
        music_file[tag] = [disc_mapping[disc_number]]
        return True


def process_directory(path: Path, args):
    logging.info("Processing: %s", path)

    # Find LOGs
    disc_numbers_to_logs = map_disc_numbers_to_values_map(
        path.glob("*.log"), args.log_encoding
    )

    # Find CUEs
    disc_numbers_to_cues = map_disc_numbers_to_values_map(
        path.glob("*.cue"), args.cue_encoding
    )

    if not disc_numbers_to_logs and not disc_numbers_to_cues:
        logging.info("No logs or cues found, skipping: %s", path)
        return

    # Find and update music files
    for file in path.glob("*.{extension}".format(extension=args.extension)):
        logging.debug("Working on file: %s", file)
        music_file = tagfile.load(file)

        # Apply log and cue
        cue_changed = apply_disc_specific_tag(
            file, music_file, disc_numbers_to_cues, "cue"
        )
        log_changed = apply_disc_specific_tag(
            file, music_file, disc_numbers_to_logs, "log"
        )

        # Save changes
        if cue_changed or log_changed:
            # It's probably a CD
            music_file["source"] = ["CD"]

            tagfile.save_atomically(file, music_file)


def run(args):
    music_path = Path(args.music_path)
    logging.debug("music_path: %s", music_path)
    logging.debug("music_path.exists: %s", music_path.exists())
    logging.debug("music_path.is_dir: %s", music_path.is_dir())
    logging.debug("music_path.is_junction: %s", music_path.is_junction())

    if not music_path.is_dir():
        logging.error("music_path is not a directory or does not exist: %s", music_path)
        sys.exit(1)

    for root, dirs, files in music_path.walk(follow_symlinks=True):
        process_directory(root, args)
        if not args.recursive:
            break
