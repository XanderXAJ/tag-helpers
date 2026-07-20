"""
Tags files with logs and cuesheets that correspond to their disc.

Note: It assumes one release per directory.
"""

import codecs
import logging
import re
import sys
from pathlib import Path

from bs4 import UnicodeDammit

from tag_helpers import tagfile

# Case-insensitive disc-matching regex
DISC_NUMBER_REGEX = re.compile(r"(?i)(?:dis[ck]|cd) ?(?P<disc>[0-9]+)")

# Matches the disc number in a DISCNUMBER tag, which may carry a total, e.g. `1/2`
DISC_TAG_REGEX = re.compile(r"^(?P<disc>[0-9]+)(?:/[0-9]+)?$")


def find_disc_number(file):
    """Attempts to find the disc number in a file's name, returns None if none is found"""
    match = DISC_NUMBER_REGEX.search(file.name)

    if match is not None:
        return int(match.group("disc"))

    return None


# Byte order marks, longest first so UTF-32's mark is not mistaken for UTF-16's
BYTE_ORDER_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
    (codecs.BOM_UTF8, "utf-8-sig"),
)

# Decodes any byte sequence without error, so it can only ever be the last resort
FALLBACK_ENCODING = "windows-1252"


def detect_byte_order_mark(raw):
    """Returns the encoding named by the file's byte order mark, or None if it has none.

    The codec is the BOM-aware one, so it consumes the mark rather than leaking it
    into the text as a zero-width no-break space.
    """
    for mark, encoding in BYTE_ORDER_MARKS:
        if raw.startswith(mark):
            return encoding

    return None


def detect_bom_less_utf_16(raw):
    """Guesses the UTF-16 variant of BOM-less text, or returns None if it looks like neither.

    Log and cue files are near enough entirely ASCII, so under UTF-16 every other byte
    is a NUL. Which half of each pair holds them gives away the endianness.
    """
    pairs = raw[: len(raw) - len(raw) % 2]
    if not pairs:
        return None

    little_endian = pairs[1::2]
    big_endian = pairs[0::2]

    if little_endian.count(0) > len(little_endian) / 2:
        return "utf-16-le"

    if big_endian.count(0) > len(big_endian) / 2:
        return "utf-16-be"

    return None


def candidate_encodings(raw, encodings):
    """Yields the encodings to try, in the order they should be tried.

    A byte order mark is authoritative, so it wins outright. Otherwise UTF-16 is
    sniffed, then strict UTF-8 is tried — both are self-validating, unlike the
    single-byte encodings — before falling back to the caller's own list.
    """
    byte_order_mark = detect_byte_order_mark(raw)
    if byte_order_mark is not None:
        yield byte_order_mark
        return

    bom_less_utf_16 = detect_bom_less_utf_16(raw)
    if bom_less_utf_16 is not None:
        yield bom_less_utf_16

    yield "utf-8"
    yield from encodings
    yield FALLBACK_ENCODING


def read_text_from_file(file, encodings):
    """Reads text from the passed file, leaving the file itself untouched.

    Tries each candidate encoding in turn, influenced by the passed list of encodings,
    and falls back to Unicode, Dammit if every one of them is rejected.
    """
    with file.open(mode="br") as handle:
        raw = handle.read()

    for encoding in candidate_encodings(raw, encodings):
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

        logging.debug("%s decoded as: %s", file, encoding)
        logging.debug(text)
        return text

    unicode = UnicodeDammit(raw, user_encodings=encodings)
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

    disc_tag = music_file["discnumber"][0]
    disc_match = DISC_TAG_REGEX.match(disc_tag)
    if disc_match is None:
        logging.info(
            "Could not read a disc number from %s, skipping %s", disc_tag, path
        )
        return False

    disc_number = int(disc_match.group("disc"))
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
