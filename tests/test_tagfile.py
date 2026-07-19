import pytest

from tag_helpers import tagfile


class StubMusicFile:
    """Stands in for a mutagen file. Records what it was given, writes a payload."""

    def __init__(self, payload):
        self.payload = payload
        self.saw_original = None

    def save(self, fileobj):
        fileobj.seek(0)
        self.saw_original = fileobj.read()
        fileobj.seek(0)
        fileobj.truncate()
        fileobj.write(self.payload)


def test_save_atomically_writes_payload_to_path(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")

    tagfile.save_atomically(path, StubMusicFile(b"new contents"))

    assert path.read_bytes() == b"new contents"


def test_save_atomically_gives_mutagen_the_original_contents(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")
    stub = StubMusicFile(b"new contents")

    tagfile.save_atomically(path, stub)

    assert stub.saw_original == b"original contents"


def test_save_atomically_exits_on_broken_pipe(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")

    class Broken:
        def save(self, fileobj):
            raise BrokenPipeError

    with pytest.raises(SystemExit) as exc:
        tagfile.save_atomically(path, Broken())

    assert exc.value.code == 1


def test_save_atomically_exits_on_keyboard_interrupt(tmp_path):
    path = tmp_path / "track.flac"
    path.write_bytes(b"original contents")

    class Interrupting:
        def save(self, fileobj):
            raise KeyboardInterrupt

    with pytest.raises(SystemExit) as exc:
        tagfile.save_atomically(path, Interrupting())

    assert exc.value.code == 1
