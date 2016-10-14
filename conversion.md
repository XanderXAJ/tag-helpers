I've been thinking recently that it might be nice to have a daemon that monitors changes to my lossless music library and automatically convert/delete lossy files as necessary.

I'll call these the Lossless library and Lossy library.

I'll attempt to list the problems that need solving.

# Change detection

- Need some way of comparing two libraries together
- Comparing directory names, assuming they are the same, is a quick way to determine down to an album level whether something has changed
    - This would seem like a reasonable limitation initially
    - If the directory is only in the Lossless library, convert it
    - If the directory is only in the Lossy library, delete it
    - Pros:
        - Albums being renamed poses no problems
    - Cons:
        - Does not cover tags being changed
        - Requires same/similar directory structure
- Perhaps file modification dates could be considered
    - Assume directory structure and file names are the same initially?
        - No tag reading required...
    - If only the Lossless file exists, convert
    - If only the Lossy file exists, delete
    - If both exist and the Lossless file is newer, convert
    - If both exist and the Lossy file is newer, skip
    - Pros:
        - Will detect tag changes in Lossless files
        - Per file granularity
            - Could even just get the latest modification per directory if that would be simpler
    - Cons:
        - Requires the same/similar file structure
- Tags could possibly be compared for track-level change detection
    - In my use case I have FLAC tags, MP4 tags and ID3v2.4 tags
    - `pytaglib` may be useful here
        - Album art is completely unsupported
        - It seems to support FLAC well:
        ```
        >>> ll = taglib.File("musictmp/Devil May Cry 2/1-01 Dance With Devils.flac")
        >>> ll.tags
        {'MUSICBRAINZ_ALBUMARTISTID': ['67ac0113-5e1c-4a1f-b9d4-44d6c6c834f4'], 'DATE': ['2004-10-15'], 'TRACKNUMBER': ['1'], 'SCRIPT': ['Latn'], 'ARTIST': ['Masato Kouda', 'Tetsuya Shibata', 'Satoshi Ise'], 'REPLAYGAIN_TRACK_GAIN': ['-10.00 dB'], 'REPLAYGAIN_ALBUM_PEAK': ['1.000000'], 'TITLE': ['Dance With Devils'], 'ARTISTSORT': ['MK, TS, SI'], 'MUSICIP_PUID': ['9fec51c4-7c69-4fa3-fe3f-fda857caf737'], 'REPLAYGAIN_ALBUM_GAIN': ['-9.28 dB'], 'LANGUAGE': ['eng'], 'RELEASECOUNTRY': ['JP'], 'DISCTOTAL': ['2'], 'ALBUMARTIST': ['Various'], 'TRACKTOTAL': ['25'], 'ALBUM': ['Devil May Cry 2'], 'MUSICBRAINZ_TRACKID': ['0f4b2dbb-8fbe-47a1-a960-f9c9b407203a'], 'DISCNUMBER': ['1'], 'RELEASETYPE': ['soundtrack'], 'ALBUMARTISTSORT': ['MK, TS, SI'], 'MUSICBRAINZ_ALBUMID': ['d3763e0d-8697-4ff1-8dd1-1ea53cd3cf07'], 'MUSICBRAINZ_ARTISTID': ['67ac0113-5e1c-4a1f-b9d4-44d6c6c834f4'], 'RELEASESTATUS': ['official'], 'REPLAYGAIN_TRACK_PEAK': ['0.989502'], 'GENRE': ['Game Soundtrack']}
        >>> ll.unsupported
        []
        ```
        - It seems to support M4A less well:
        ```
        >>> ly = taglib.File("musiclossy/Devil May Cry 2/1-01 Dance With Devils.m4a")
        >>> ly.tags
        {'TRACKNUMBER': ['1/25'], 'TITLE': ['Dance With Devils'], 'DATE': ['2004-10-15'], 'ENCODEDBY': ['Nero AAC codec / 1.5.4.0'], 'DISCNUMBER': ['1/2'], 'ALBUM': ['Devil May Cry 2'], 'ARTIST': ['Masato Kouda'], 'GENRE': ['Game Soundtrack']}
        >>> ly.close()
        >>> ly = taglib.File("musiclossy/Devil May Cry 2/1-01 Dance With Devils.m4a")
        >>> ly.unsupported
        ['----:com.apple.iTunes:albumartistsort', '----:com.apple.iTunes:artistsort', '----:com.apple.iTunes:cdec', '----:com.apple.iTunes:iTunSMPB', '----:com.apple.iTunes:language', '----:com.apple.iTunes:musicbrainz_albumartistid', '----:com.apple.iTunes:musicbrainz_albumid', '----:com.apple.iTunes:musicbrainz_artistid', '----:com.apple.iTunes:musicbrainz_trackid', '----:com.apple.iTunes:musicip_puid', '----:com.apple.iTunes:releasecountry', '----:com.apple.iTunes:releasestatus', '----:com.apple.iTunes:releasetype', '----:com.apple.iTunes:replaygain_album_gain', '----:com.apple.iTunes:replaygain_track_gain', '----:com.apple.iTunes:script', 'aART']
        ```

# File modification detection

- How can this be done?
    - Does it work well in any particular language?  Python?

# Conversion

- I currently use Foobar2000 to perform all conversions; to FLAC, to M4A, to OGG
    - After fb2k uses the encoder to create the encoding, it then applies tags, album art and replaygain
        - This means that, if I want the same level of tagging, this daemon would need to also apply tags after encoding
- [There are a number AAC encoders][aac-encoders] out there, including some for Linux
    - I currently use the Nero AAC encoder on Windows, which also has a Linux version, but is also getting a bit old

[aac-encoders]: http://wiki.hydrogenaud.io/index.php?title=AAC_encoders
