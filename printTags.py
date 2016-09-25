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
if not music_path.exists():
    print('music_path does not exist', file=sys.stderr)
    exit(1)

# Print tags for all files
for path in music_path.glob('**/*.flac'):
    file = taglib.File(str(path))
    print('\n\n\n', str(path), ': ')
    pp.pprint(file.tags);
    pp.pprint(file.unsupported)
