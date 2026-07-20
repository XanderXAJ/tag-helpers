from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4Tags
from mutagen.flac import VCFLACDict

from tag_helpers.operations import (
    AlbumArtistMigrationOperation,
    AlbumArtistReductionOperation,
    PrintTagsOperation,
    RemoveTags,
    SplitNumberTotals,
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


def test_reduction_falls_back_to_the_spaced_tag():
    """The docstring promises ALBUM ARTIST is checked as well as ALBUMARTIST."""
    check = AlbumArtistReductionOperation().check

    assert check({"ALBUM ARTIST": ["Various", "Bob"]}) is True
    assert check({"ALBUM ARTIST": ["Bob", "Alice"]}) is False


def test_reduction_writes_to_the_unspaced_tag_from_a_spaced_source():
    file = {"ALBUM ARTIST": ["Various", "Bob"]}

    AlbumArtistReductionOperation().execute(file)

    assert file["ALBUMARTIST"] == ["Various"]


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


def test_split_checks_only_for_combined_values():
    check = SplitNumberTotals().check
    assert check({"DISCNUMBER": ["1/2"]}) is True
    assert check({"TRACKNUMBER": ["3/10"]}) is True
    assert check({"DISCNUMBER": ["1"], "DISCTOTAL": ["2"]}) is False
    assert check({}) is False


def test_split_separates_the_total_into_its_own_tag():
    file = {"DISCNUMBER": ["1/2"], "TRACKNUMBER": ["3/10"]}

    SplitNumberTotals().execute(file)

    assert file == {
        "DISCNUMBER": ["1"],
        "DISCTOTAL": ["2"],
        "TRACKNUMBER": ["3"],
        "TRACKTOTAL": ["10"],
    }


def test_split_strips_zero_padding():
    file = {"DISCNUMBER": ["01/02"], "TRACKNUMBER": ["003/010"]}

    SplitNumberTotals().execute(file)

    assert file == {
        "DISCNUMBER": ["1"],
        "DISCTOTAL": ["2"],
        "TRACKNUMBER": ["3"],
        "TRACKTOTAL": ["10"],
    }


def test_split_matches_a_padded_total_against_an_unpadded_existing_one():
    """`2` and `02` are the same total, so this is not a conflict."""
    file = {"DISCNUMBER": ["1/2"], "DISCTOTAL": ["02"]}

    SplitNumberTotals().execute(file)

    assert file == {"DISCNUMBER": ["1"], "DISCTOTAL": ["2"]}


def test_split_handles_zero_padded_zero():
    file = {"DISCNUMBER": ["00/00"]}

    SplitNumberTotals().execute(file)

    assert file == {"DISCNUMBER": ["0"], "DISCTOTAL": ["0"]}


def test_split_ignores_non_numeric_and_multi_valued_tags():
    check = SplitNumberTotals().check
    assert check({"DISCNUMBER": ["A/B"]}) is False
    assert check({"DISCNUMBER": ["1/"]}) is False
    assert check({"DISCNUMBER": ["1/2", "3/4"]}) is False


def test_split_keeps_a_differing_existing_total():
    """An existing total that disagrees is a conflict, not something to overwrite."""
    file = {"DISCNUMBER": ["1/2"], "DISCTOTAL": ["5"]}

    SplitNumberTotals().execute(file)

    assert file == {"DISCNUMBER": ["1"], "DISCTOTAL": ["5"]}


def test_split_is_idempotent():
    file = {"DISCNUMBER": ["1/2"]}
    operation = SplitNumberTotals()

    operation.safe_execute(file)
    operation.safe_execute(file)

    assert file == {"DISCNUMBER": ["1"], "DISCTOTAL": ["2"]}
    assert operation.check(file) is False


def test_split_leaves_id3_and_mp4_alone():
    """`number/total` is the native ID3/MP4 form, and neither accepts a separate total."""
    for tags in (EasyID3(), EasyMP4Tags()):
        tags["discnumber"] = ["1/2"]

        assert SplitNumberTotals().check(tags) is False


def test_split_applies_to_vorbis_comments():
    tags = VCFLACDict()
    tags["DISCNUMBER"] = ["1/2"]

    SplitNumberTotals().safe_execute(tags)

    assert tags.as_dict() == {"discnumber": ["1"], "disctotal": ["2"]}


def test_operation_library_uses_kebab_case_keys():
    assert set(operation_library) == {
        "album-artist-migration",
        "album-artist-reduction",
        "print-tags",
        "remove-fb2k-playback-statistics",
        "remove-artists-tags",
        "remove-sort-tags",
        "split-number-totals",
    }
