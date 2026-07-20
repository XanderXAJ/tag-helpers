"""Extracts embedded pictures from music files to a destination directory.

Pictures are written to files whose names are built from a format string
containing placeholders for the file's tags and the picture slot, e.g. the
default ``{artist} - {album} ({slot})`` yields ``Daft Punk - Discovery
(Front)``.  Pictures whose formatted name and contents match an
already-extracted picture are skipped, so shared artwork (for example, the same
cover repeated across every track of an album, or across albums) is only written
once.
"""

import hashlib
import logging
import sys
from pathlib import Path

from tag_helpers import tagfile

# Human-friendly names for the standard picture slots.  The integers are the
# ID3/FLAC picture type values (mutagen exposes them via mutagen.id3.PictureType).
PICTURE_SLOT_NAMES = {
    0: "Other",
    1: "Icon",
    2: "Other Icon",
    3: "Front",
    4: "Back",
    5: "Leaflet",
    6: "Media",
    7: "Lead Artist",
    8: "Artist",
    9: "Conductor",
    10: "Band",
    11: "Composer",
    12: "Lyricist",
    13: "Recording Location",
    14: "During Recording",
    15: "During Performance",
    16: "Screen Capture",
    17: "Bright Coloured Fish",
    18: "Illustration",
    19: "Band Logo",
    20: "Publisher Logo",
}

DEFAULT_FORMAT = "{artist} - {album} ({slot})"

MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
}


class _DefaultingDict(dict):
    """Maps missing format placeholders to an empty string rather than erroring."""

    def __missing__(self, key):
        logging.debug("Format placeholder %r has no value; using empty string", key)
        return ""


def resolve_paths(source, extension):
    """Yields the music files under source (a directory), recursing all files."""
    source = Path(source)
    if source.is_dir():
        return source.glob("**/*.{extension}".format(extension=extension))
    if source.is_file():
        return iter([source])

    print("source does not exist", file=sys.stderr)
    sys.exit(1)


def pictures_for(music_file):
    """Returns the embedded pictures for a mutagen file, or [] if it has none."""
    return list(getattr(music_file, "pictures", []) or [])


def slot_name(picture):
    """Returns a human-friendly name for a picture's slot."""
    return PICTURE_SLOT_NAMES.get(picture.type, "Other")


def extension_for(picture):
    """Returns a file extension (including the dot) for a picture's MIME type."""
    mime = (picture.mime or "").lower()
    if mime in MIME_EXTENSIONS:
        return MIME_EXTENSIONS[mime]
    if "/" in mime:
        return "." + mime.rsplit("/", 1)[1]
    return ".img"


def _sanitise(name):
    """Replaces path separators so a formatted name stays a single filename."""
    return name.replace("/", "_").replace("\\", "_").strip()


def format_fields(music_file, picture):
    """Builds the placeholder values available to the format string."""
    fields = {}
    tags = getattr(music_file, "tags", None) or {}
    for key, value in tags.items():
        if isinstance(value, list):
            value = value[0] if value else ""
        fields[str(key).lower()] = str(value)
    fields["slot"] = slot_name(picture)
    return fields


def destination_name(music_file, picture, format_string):
    """Builds the destination filename (with extension) for a picture."""
    fields = format_fields(music_file, picture)
    stem = format_string.format_map(_DefaultingDict(fields))
    return _sanitise(stem) + extension_for(picture)


def run(args):
    source = Path(args.source)
    destination = Path(args.destination)
    format_string = args.format

    paths = resolve_paths(source, args.extension)

    destination.mkdir(parents=True, exist_ok=True)

    # Remembers the SHA-1 of the contents already written to each destination
    # path so identical pictures are skipped and differing ones do not clobber.
    written = {}
    extracted = 0

    for path in paths:
        music_file = tagfile.load(path)
        if music_file is None:
            logging.debug("Skipping unreadable file %s", path)
            continue

        for picture in pictures_for(music_file):
            name = destination_name(music_file, picture, format_string)
            dest = destination / name
            digest = hashlib.sha1(picture.data).hexdigest()

            existing = written.get(dest)
            if existing is None and dest.exists():
                existing = hashlib.sha1(dest.read_bytes()).hexdigest()

            if existing == digest:
                logging.info("Skipping duplicate %s (from %s)", dest, path)
                continue

            if existing is not None:
                # Same formatted name but different contents: keep both by
                # disambiguating with a short content hash.
                dest = dest.with_name(
                    "{stem} [{hash}]{suffix}".format(
                        stem=dest.stem, hash=digest[:8], suffix=dest.suffix
                    )
                )
                if written.get(dest) == digest or (
                    dest.exists()
                    and hashlib.sha1(dest.read_bytes()).hexdigest() == digest
                ):
                    logging.info("Skipping duplicate %s (from %s)", dest, path)
                    written[dest] = digest
                    continue

            dest.write_bytes(picture.data)
            written[dest] = digest
            extracted += 1
            print("Extracted", dest, "from", path)

    logging.info("Extracted %d picture(s) to %s", extracted, destination)
