"""Command line entry point for tag-helpers."""

import argparse
import logging
import signal
import sys

from tag_helpers import extract_pictures, manage_tags, print_tags, tag_logs_and_cues
from tag_helpers.operations import operation_library


def sigint_handler(signal, frame):
    print("Interrupt received, stopping...", file=sys.stderr)
    sys.exit(1)


def build_parser():
    """Builds the argument parser for tag-helpers and its subcommands."""
    # Options every subcommand shares, supplied via parent parsers
    logging_opts = argparse.ArgumentParser(add_help=False)
    logging_opts.add_argument(
        "--log-level",
        help="Set logging level",
        default="WARNING",
        type=str.upper,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
    )

    # Tag operations act on one file type at a time; extract-pictures instead
    # walks every file it can read, so it does not take --extension.
    shared = argparse.ArgumentParser(add_help=False, parents=[logging_opts])
    shared.add_argument("-e", "--extension", default="flac")

    # Subcommands that operate on a single music path add it on top of `shared`.
    common = argparse.ArgumentParser(add_help=False, parents=[shared])
    common.add_argument("music_path")

    parser = argparse.ArgumentParser(
        prog="tag-helpers", description="Scripts to help with tagging music files"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    print_parser = subparsers.add_parser(
        "print",
        parents=[common],
        help="Pretty print tags for all music files under a path",
    )
    print_parser.set_defaults(func=print_tags.run)

    manage_parser = subparsers.add_parser(
        "manage",
        parents=[common],
        help="Run selected tag operations over a file or directory",
    )
    manage_parser.add_argument(
        "-o",
        "--operation",
        choices=operation_library,
        action="append",
        required=True,
    )
    manage_parser.set_defaults(func=manage_tags.run)

    logs_and_cues_parser = subparsers.add_parser(
        "tag-logs-and-cues",
        parents=[common],
        help="Tag music files with the *.log and *.cue files for their disc",
    )
    logs_and_cues_parser.add_argument("-R", "--recursive", action="store_true")
    logs_and_cues_parser.add_argument(
        "-c", "--cue-encoding", action="append", default=["windows-1252", "shift_jis"]
    )
    logs_and_cues_parser.add_argument(
        "-l", "--log-encoding", action="append", default=[]
    )
    logs_and_cues_parser.set_defaults(func=tag_logs_and_cues.run)

    extract_parser = subparsers.add_parser(
        "extract-pictures",
        parents=[logging_opts],
        help="Extract embedded pictures from files to a destination directory",
    )
    extract_parser.add_argument("source", help="Directory (or file) to search")
    extract_parser.add_argument(
        "destination", help="Directory to write extracted pictures into"
    )
    extract_parser.add_argument(
        "-f",
        "--format",
        default=extract_pictures.DEFAULT_FORMAT,
        help=(
            "Format for destination file names, with placeholders for tags and "
            "{slot} for the picture slot (default: %(default)r)"
        ),
    )
    extract_parser.set_defaults(func=extract_pictures.run)

    return parser


def main():
    """Main entrypoint"""
    # Handle keyboard interrupts by default
    signal.signal(signal.SIGINT, sigint_handler)

    args = build_parser().parse_args()

    # Set logging level
    logging.basicConfig(level=logging.getLevelName(args.log_level))

    # Log configuration
    logging.info("Configuration:")
    for name, value in sorted(vars(args).items()):
        if name != "func":
            logging.info("  %s: %s", name, value)

    args.func(args)


if __name__ == "__main__":
    main()
