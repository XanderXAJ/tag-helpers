"""Loading and safely saving tagged audio files.

Every write in the package goes through save_atomically.
"""
import logging
import os
import shutil
import sys

import mutagen
from atomicwrites import atomic_write


def load(path):
    """Loads a music file with mutagen's easy tag interface."""
    return mutagen.File(str(path), easy=True)


def save_atomically(path, music_file):
    """Saves changes to a mutagen music file as safely and atomically as possible"""
    try:
        # Mutagen writes directly to the file in question.  If something should go
        # wrong (e.g. power failure, shutdown), the file would be left in an undefined
        # (and probably corrupt state).  To minimise the chances of this, copy
        # contents to a temp file and swap the original and temp files as atomically
        # as possible on the platform. Atomic Writes performs the swap.
        with atomic_write(str(path), overwrite=True, mode="w+b") as temp_file:
            # Copy original file in to temp file
            with open(str(path), "rb") as orig_file:
                shutil.copyfileobj(orig_file, temp_file)

            # Seek back to beginning of file
            temp_file.seek(0, os.SEEK_SET)

            # Write modifications to temp file
            music_file.save(temp_file)
    except (KeyboardInterrupt, SystemExit):
        logging.critical("Interrupt received, stopping...")
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(1)
