"""Tag operations applied by the `manage` subcommand.

Each operation reports whether a file needs it (check) and applies it (execute).
"""


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
    "remove-sort-tags": RemoveTags(
        tags=["ALBUMARTISTSORT", "ALBUMSORT", "ARTISTSORT", "COMPOSERSORT", "TITLESORT"]
    ),
}
