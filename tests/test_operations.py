from tag_helpers.operations import (
    AlbumArtistMigrationOperation,
    AlbumArtistReductionOperation,
    PrintTagsOperation,
    RemoveTags,
    operation_library,
)


def test_migration_checks_for_spaced_tag():
    assert AlbumArtistMigrationOperation().check({"ALBUM ARTIST": ["Bob"]}) is True
    assert AlbumArtistMigrationOperation().check({"ALBUMARTIST": ["Bob"]}) is False


def test_migration_moves_tag():
    file = {"ALBUM ARTIST": ["Bob"]}

    AlbumArtistMigrationOperation().execute(file)

    assert file == {"ALBUMARTIST": ["Bob"]}


def test_reduction_triggers_on_various_among_several():
    check = AlbumArtistReductionOperation().check
    assert check({"ALBUMARTIST": ["Various", "Bob"]}) is True
    assert check({"ALBUMARTIST": ["various artists", "Bob"]}) is True


def test_reduction_ignores_single_or_various_free_artists():
    check = AlbumArtistReductionOperation().check
    assert check({"ALBUMARTIST": ["Various"]}) is False
    assert check({"ALBUMARTIST": ["Bob", "Alice"]}) is False
    assert check({}) is False


def test_reduction_collapses_to_various():
    file = {"ALBUMARTIST": ["Various", "Bob"]}

    AlbumArtistReductionOperation().execute(file)

    assert file == {"ALBUMARTIST": ["Various"]}


def test_remove_tags_checks_and_removes_only_present_tags():
    operation = RemoveTags(tags=["RATING", "PLAY_COUNT"])
    file = {"RATING": ["5"], "TITLE": ["Song"]}

    assert operation.check(file) is True
    operation.execute(file)

    assert file == {"TITLE": ["Song"]}


def test_remove_tags_check_false_when_absent():
    assert RemoveTags(tags=["RATING"]).check({"TITLE": ["Song"]}) is False


def test_print_tags_always_checks_true_and_prints(capsys):
    class Printable(dict):
        def pprint(self):
            return "TITLE=Song"

    file = Printable()
    assert PrintTagsOperation().check(file) is True

    PrintTagsOperation().execute(file)

    assert capsys.readouterr().out == "TITLE=Song\n"


def test_safe_execute_skips_when_check_fails():
    file = {"TITLE": ["Song"]}

    RemoveTags(tags=["RATING"]).safe_execute(file)

    assert file == {"TITLE": ["Song"]}


def test_operation_library_uses_kebab_case_keys():
    assert set(operation_library) == {
        "album-artist-migration",
        "album-artist-reduction",
        "print-tags",
        "remove-fb2k-playback-statistics",
        "remove-artists-tags",
        "remove-sort-tags",
    }
