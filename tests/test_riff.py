from tag_helpers import riff
from tests.wav_fixtures import make_wav


def test_inspect_healthy_wav_needs_no_fix(tmp_path):
    report = riff.inspect(make_wav(tmp_path / "ok.wav"))

    assert report is not None
    assert report.needs_fix is False
    assert report.verdict == "RECOVERABLE"


def test_inspect_flags_inflated_header_as_recoverable(tmp_path):
    report = riff.inspect(
        make_wav(tmp_path / "inflated.wav", declared_riff_size=10_000_000)
    )

    assert report.needs_fix is True
    assert report.header_inflated is True
    assert report.truncated is False
    assert report.verdict == "RECOVERABLE"
    assert report.missing_bytes == 0


def test_inspect_flags_truncated_data_and_measures_loss(tmp_path):
    report = riff.inspect(
        make_wav(
            tmp_path / "cut.wav",
            samples=b"\x00" * 100,
            declared_data_size=1100,
            byte_rate=1000,
        )
    )

    assert report.needs_fix is True
    assert report.truncated is True
    assert report.verdict == "TRUNCATED"
    assert report.missing_bytes == 1000
    assert report.missing_seconds == 1.0


def test_inspect_returns_none_for_non_wav(tmp_path):
    path = tmp_path / "nope.wav"
    path.write_bytes(b"NOT A RIFF FILE AT ALL")

    assert riff.inspect(path) is None
