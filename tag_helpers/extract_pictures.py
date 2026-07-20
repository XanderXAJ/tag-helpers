"""Extracts embedded pictures from music files to a destination directory.

Pictures are written to files whose names are built from a format string
containing placeholders for the file's tags and the picture slot, e.g. the
default ``{albumartist} - {album} ({slot})`` yields ``Daft Punk - Discovery
(Front)``.  ``{albumartist}`` falls back to the track artist when the file has
no album artist.  Pictures whose formatted name and contents match an
already-extracted picture are skipped, so shared artwork (for example, the same
cover repeated across every track of an album, or across albums) is only written
once.
"""

import hashlib
import logging
import sys
from pathlib import Path

from mutagen.id3 import ID3, PictureType
from mutagen.mp4 import MP4Cover, MP4Tags

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

DEFAULT_FORMAT = "{albumartist} - {album} ({slot})"

MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
}

# A FLAC metadata block's length is a 24-bit field, so the whole PICTURE block
# (fixed fields + mime + description + image bytes) must fit in 2**24 - 1 bytes.
# Art bigger than this is what makes foobar report "Picture too large for FLAC".
FLAC_PICTURE_BLOCK_LIMIT = (1 << 24) - 1

# Eight 4-byte integers: type, mime-length, desc-length, width, height, depth,
# colours, data-length.
_PICTURE_FIXED_BYTES = 8 * 4


def flac_picture_block_size(picture):
    """Bytes the picture would occupy as a FLAC PICTURE metadata block body."""
    mime = (getattr(picture, "mime", "") or "").encode("ascii", "replace")
    desc = (getattr(picture, "desc", "") or "").encode("utf-8")
    return _PICTURE_FIXED_BYTES + len(mime) + len(desc) + len(picture.data)


def is_oversized_for_flac(picture):
    """True when the picture would exceed FLAC's PICTURE block size limit."""
    return flac_picture_block_size(picture) > FLAC_PICTURE_BLOCK_LIMIT


class _DefaultingDict(dict):
    """Maps missing format placeholders to an empty string rather than erroring."""

    def __missing__(self, key):
        logging.debug("Format placeholder %r has no value; using empty string", key)
        return ""


def resolve_paths(source):
    """Yields every file under source (a directory), recursing.

    Files are not filtered by extension: a folder typically mixes formats
    (FLAC, WAV, MP3, ...), and mutagen decides per file what it can read, so
    ``run`` simply skips anything it cannot open as a tagged audio file.
    """
    source = Path(source)
    if source.is_dir():
        return (path for path in source.glob("**/*") if path.is_file())
    if source.is_file():
        return iter([source])

    print("source does not exist", file=sys.stderr)
    sys.exit(1)


class _Picture:
    """Adapts a container-specific cover to the FLAC Picture attributes we use."""

    def __init__(self, type, mime, data):
        self.type = type
        self.mime = mime
        self.data = data


# MP4 has no picture slot concept, so its covers are all treated as front covers.
MP4_COVER_MIMES = {
    MP4Cover.FORMAT_JPEG: "image/jpeg",
    MP4Cover.FORMAT_PNG: "image/png",
}


def pictures_for(music_file):
    """Returns the embedded pictures for a mutagen file, or [] if it has none.

    Each container stores artwork differently: FLAC exposes a .pictures list,
    ID3-based formats (MP3, WAV, AIFF) use APIC frames, and MP4 uses covr atoms.
    """
    pictures = getattr(music_file, "pictures", None)
    if pictures:
        return list(pictures)

    tags = getattr(music_file, "tags", None)
    if isinstance(tags, ID3):
        return list(tags.getall("APIC"))
    if isinstance(tags, MP4Tags):
        return [
            _Picture(
                PictureType.COVER_FRONT,
                MP4_COVER_MIMES.get(cover.imageformat, ""),
                bytes(cover),
            )
            for cover in tags.get("covr", [])
        ]
    return []


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


# Native tag names are container-specific, so they are normalised to the
# Vorbis-style names the format string uses.  Only the placeholders worth naming
# a picture after are mapped; anything else stays available under its raw name.
ID3_FIELD_NAMES = {
    "TALB": "album",
    "TPE1": "artist",
    "TPE2": "albumartist",
    "TIT2": "title",
    "TCON": "genre",
    "TDRC": "date",
    "TRCK": "tracknumber",
    "TPOS": "discnumber",
}

MP4_FIELD_NAMES = {
    "\xa9alb": "album",
    "\xa9ART": "artist",
    "aART": "albumartist",
    "\xa9nam": "title",
    "\xa9gen": "genre",
    "\xa9day": "date",
}


def _first(value):
    """Reduces a possibly-multivalued tag to a single string."""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value)


def text_fields(music_file):
    """Returns the file's text tags keyed by normalised, lowercase names."""
    tags = getattr(music_file, "tags", None) or {}
    fields = {}

    if isinstance(tags, ID3):
        for frame_id, name in ID3_FIELD_NAMES.items():
            frame = tags.getall(frame_id)
            if frame and getattr(frame[0], "text", None):
                fields[name] = _first(frame[0].text)
        return fields

    if isinstance(tags, MP4Tags):
        for atom, name in MP4_FIELD_NAMES.items():
            if tags.get(atom):
                fields[name] = _first(tags[atom])
        return fields

    # Vorbis comments (FLAC, Ogg) already use the names the format string wants.
    for key, value in tags.items():
        fields[str(key).lower()] = _first(value)
    return fields


def format_fields(music_file, picture):
    """Builds the placeholder values available to the format string."""
    fields = text_fields(music_file)
    # Compilations and albums with guest artists vary the artist per track, which
    # would write a copy of the same cover per artist.  Prefer the album artist so
    # shared artwork lands on one name and deduplicates.
    fields["albumartist"] = fields.get("albumartist") or fields.get("artist", "")
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

    paths = resolve_paths(source)

    destination.mkdir(parents=True, exist_ok=True)

    # Remembers the SHA-1 of the contents already written to each destination
    # path so identical pictures are skipped and differing ones do not clobber.
    written = {}
    extracted = 0

    for path in paths:
        music_file = tagfile.load_native(path)
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
