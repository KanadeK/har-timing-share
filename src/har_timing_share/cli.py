from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .core import HarError, load_har, project_har
from .render import render_html


def positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _write_new(path: str, text: str) -> None:
    """Exclusive creation prevents overwriting the source, an existing file or link."""
    destination = Path(path)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project HAR into a performance-only report. No network access."
    )
    parser.add_argument("input", help="local UTF-8 HAR file")
    parser.add_argument(
        "--output", "-o", required=True, help="new output path; '-' for JSON stdout"
    )
    parser.add_argument("--format", choices=("html", "json"), default="html")
    parser.add_argument("--max-bytes", type=positive, default=64 * 1024 * 1024)
    parser.add_argument("--max-entries", type=positive, default=10_000)
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.output == "-" and args.format != "json":
        parser.error("stdout output requires --format json")
    try:
        report = project_har(
            load_har(args.input, max_bytes=args.max_bytes), max_entries=args.max_entries
        )
        text = (
            json.dumps(report, indent=2, allow_nan=False) + "\n"
            if args.format == "json"
            else render_html(report)
        )
        if args.output == "-":
            sys.stdout.write(text)
        else:
            _write_new(args.output, text)
            print("Wrote performance report.")
        return 0
    except FileExistsError:
        print(
            "Output already exists. Choose a new path; existing files are never overwritten.",
            file=sys.stderr,
        )
    except HarError as error:
        print(f"Invalid HAR: {error}", file=sys.stderr)
    except OSError:
        print(
            "Could not write the output. Check permissions, directory and free space.",
            file=sys.stderr,
        )
    except KeyboardInterrupt:
        return 130
    return 2
