"""Command line entry point for tag-helpers."""

import argparse
import logging
import signal
import sys

from tag_helpers import manage_tags, print_tags, tag_logs_and_cues
from tag_helpers.operations import operation_library


def sigint_handler(signal, frame):
    print("Interrupt received, stopping...", file=sys.stderr)
    sys.exit(1)


def build_parser():
    """Builds the argument parser for tag-helpers and its subcommands."""
    # Options every subcommand shares, supplied via a parent parser
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("music_path")
    common.add_argument("-e", "--extension", default="flac")
    common.add_argument(
        "--log-level",
        help="Set logging level",
        default="WARNING",
        type=str.upper,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
    )

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
