import pytest

from tag_helpers import cli


def test_print_subcommand_parses_shared_options():
    args = cli.build_parser().parse_args(["print", "/music", "-e", "mp3"])

    assert args.music_path == "/music"
    assert args.extension == "mp3"
    assert args.func is not None


def test_extension_defaults_to_flac():
    args = cli.build_parser().parse_args(["print", "/music"])

    assert args.extension == "flac"


def test_log_level_available_on_every_subcommand():
    parser = cli.build_parser()

    for argv in (
        ["print", "/music"],
        ["manage", "/music", "-o", "remove-sort-tags"],
        ["tag-logs-and-cues", "/music"],
    ):
        assert parser.parse_args(argv).log_level == "WARNING"


def test_log_level_is_upper_cased():
    args = cli.build_parser().parse_args(["print", "/music", "--log-level", "debug"])

    assert args.log_level == "DEBUG"


def test_manage_accumulates_operations():
    args = cli.build_parser().parse_args(
        ["manage", "/music", "-o", "remove-sort-tags", "-o", "print-tags"]
    )

    assert args.operation == ["remove-sort-tags", "print-tags"]


def test_manage_rejects_unknown_operation():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["manage", "/music", "-o", "nonsense"])


def test_manage_requires_at_least_one_operation():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["manage", "/music"])


def test_tag_logs_and_cues_parses_its_own_options():
    args = cli.build_parser().parse_args(
        ["tag-logs-and-cues", "/music", "-R", "-l", "utf-8"]
    )

    assert args.recursive is True
    assert args.log_encoding == ["utf-8"]
    assert args.cue_encoding == ["windows-1252", "shift_jis"]


def test_tag_logs_and_cues_recursive_defaults_off():
    args = cli.build_parser().parse_args(["tag-logs-and-cues", "/music"])

    assert args.recursive is False


def test_subcommand_is_required():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_sigint_handler_reports_and_exits(capsys):
    """The 'Handle keyboard exceptions by default' behaviour lifted from manageTags."""
    with pytest.raises(SystemExit) as exc:
        cli.sigint_handler(None, None)

    assert exc.value.code == 1
    assert "Interrupt received, stopping..." in capsys.readouterr().err


def test_main_dispatches_to_the_chosen_subcommand(monkeypatch):
    called = []
    monkeypatch.setattr(cli.print_tags, "run", lambda args: called.append(args))
    monkeypatch.setattr("sys.argv", ["tag-helpers", "print", "/music"])

    cli.main()

    assert len(called) == 1
    assert called[0].music_path == "/music"


def test_each_subcommand_dispatches_to_its_module():
    from tag_helpers import manage_tags, print_tags, tag_logs_and_cues

    parser = cli.build_parser()

    assert parser.parse_args(["print", "/m"]).func is print_tags.run
    assert (
        parser.parse_args(["manage", "/m", "-o", "print-tags"]).func is manage_tags.run
    )
    assert parser.parse_args(["tag-logs-and-cues", "/m"]).func is tag_logs_and_cues.run


def test_check_subcommand_dispatches_to_check_module():
    from tag_helpers import check

    args = cli.build_parser().parse_args(["check", "/music"])

    assert args.music_path == "/music"
    assert args.func is check.run


def test_repair_wav_subcommand_parses_dry_run():
    from tag_helpers import repair_wav

    args = cli.build_parser().parse_args(["repair-wav", "/music", "--dry-run"])

    assert args.music_path == "/music"
    assert args.dry_run is True
    assert args.func is repair_wav.run


def test_repair_wav_dry_run_defaults_off():
    args = cli.build_parser().parse_args(["repair-wav", "/music"])

    assert args.dry_run is False
