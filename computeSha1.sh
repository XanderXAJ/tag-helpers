#!/bin/sh
find "$1" -type f ! -name 'checksums.sha1' -execdir bash -c 'pwd && sha1sum "$@" > "checksums.sha1"' - {} +
