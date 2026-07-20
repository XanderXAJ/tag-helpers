"""Tag operations applied by the `manage` subcommand.

Each operation reports whether a file needs it (check) and applies it (execute).
"""

import logging
import re

# Matches a `number/total` tag value, e.g. `1/1`, `01/02`, `3/10`
NUMBER_TOTAL_REGEX = re.compile(r"^(?P<number>[0-9]+)/(?P<total>[0-9]+)$")


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
        return "ALBUM ARTIST" in file

    def execute(self, file):
        file["ALBUMARTIST"] = file["ALBUM ARTIST"]
        del file["ALBUM ARTIST"]


class AlbumArtistReductionOperation(Operation):
    """Reduces ALBUM ARTIST/ALBUMARTIST to 'Various'"""

    def check(self, file):
        for tag in ["ALBUMARTIST", "ALBUM ARTIST"]:
            if tag in file:
                album_artists = list(map(str.lower, file[tag]))
                if len(album_artists) > 1 and (
                    "various" in album_artists or "various artists" in album_artists
                ):
                    return True
        return False

    def execute(self, file):
        file["ALBUMARTIST"] = ["Various"]


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


class SplitNumberTotals(Operation):
    """Splits `number/total` tags, e.g. DISCNUMBER `1/2` -> DISCNUMBER `1`, DISCTOTAL `2`"""

    # Maps the combined tag to the tag its total belongs in
    tags = {"DISCNUMBER": "DISCTOTAL", "TRACKNUMBER": "TRACKTOTAL"}

    def accepts_tag(self, file, tag):
        """Reports whether the file's format can store the named tag.

        mutagen's easy interfaces expose a fixed registry of the keys they map onto
        the underlying format; ID3 and MP4 have no separate total, storing
        `number/total` natively instead, so those files are left alone. Vorbis
        comments have no registry and take arbitrary tags.
        """
        for registry in ("valid_keys", "Set"):
            keys = getattr(type(file), registry, None)
            if keys is not None:
                return tag.lower() in keys

        return True

    def find_matches(self, file):
        """Yields (tag, total_tag, match) for each single-valued `number/total` tag."""
        for tag, total_tag in self.tags.items():
            if not self.accepts_tag(file, total_tag):
                continue

            values = file.get(tag)
            if values is None or len(values) != 1:
                continue

            match = NUMBER_TOTAL_REGEX.match(values[0])
            if match is not None:
                yield tag, total_tag, match

    def check(self, file):
        return any(self.find_matches(file))

    def execute(self, file):
        for tag, total_tag, match in list(self.find_matches(file)):
            number, total = match.group("number"), match.group("total")
            file[tag] = [number]

            existing = file.get(total_tag)
            if existing is None:
                file[total_tag] = [total]
            elif existing != [total]:
                logging.warning(
                    "%s is %s but %s says %s, keeping the existing %s",
                    tag,
                    match.group(0),
                    total_tag,
                    existing,
                    total_tag,
                )


class PrintTagsOperation(Operation):
    """Prints file tags"""

    def check(self, file):
        return True

    def execute(self, file):
        print(file.pprint())


operation_library = {
    "album-artist-migration": AlbumArtistMigrationOperation(),
    "album-artist-reduction": AlbumArtistReductionOperation(),
    "print-tags": PrintTagsOperation(),
    "remove-fb2k-playback-statistics": RemoveTags(
        tags=[
            "ADDED_TIMESTAMP",
            "FIRST_PLAYED_TIMESTAMP",
            "LAST_PLAYED_TIMESTAMP",
            "PLAY_COUNT",
            "RATING",
        ]
    ),
    "remove-artists-tags": RemoveTags(tags=["ARTISTS", "ALBUMARTISTS"]),
    "split-number-totals": SplitNumberTotals(),
    "remove-sort-tags": RemoveTags(
        tags=["ALBUMARTISTSORT", "ALBUMSORT", "ARTISTSORT", "COMPOSERSORT", "TITLESORT"]
    ),
}
