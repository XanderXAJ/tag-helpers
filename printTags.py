#!/usr/bin/env python3
# printTags
# Pretty prints tags for all FLAC files under a given directory.
import argparse
import taglib
from pathlib import Path

import pprint
pp = pprint.PrettyPrinter()

parser = argparse.ArgumentParser()
parser.add_argument('music_path')
args = parser.parse_args()

# Stop if music_path does not exist
music_path = Path(args.music_path)
if music_path.is_dir():
    paths = music_path.glob('**/*.flac')
elif music_path.is_file():
    paths = [music_path]
else:
    print('music_path does not exist', file=sys.stderr)
    exit(1)

# Print tags for all files
for path in paths:
    file = taglib.File(str(path))
    print('\n\n\n', str(path), ': ')
    pp.pprint(file.tags);
    pp.pprint(file.unsupported)
