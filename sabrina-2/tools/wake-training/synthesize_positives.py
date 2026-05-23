"""Synthesize positive wake-word samples via piper-sample-generator.

Thin wrapper around the upstream `piper_sample_generator` module that:

- Anchors paths to this project (``sabrina-2/tools/wake-training/data/positive/``).
- Picks a deterministic seed so retrains are reproducible.
- Supports ``--dry-run``: prints the command it would execute and exits 0
  without invoking the heavy synth pipeline.

The default invocation matches what ``research/2026-05-05-wake-word-training-pipeline.md``
recommends: ``python -m piper_sample_generator 'Hey Sabrina'`` plus a sample
count and an output directory. The full prosody/speaker grid is consolidated
inside ``piper_sample_generator`` itself; this script does not hand-roll
that loop.

Run this from the repo root in a WSL2 / Linux environment with
``requirements-training.txt`` installed:

    python sabrina-2/tools/wake-training/synthesize_positives.py

For a no-op preview:

    python sabrina-2/tools/wake-training/synthesize_positives.py --dry-run

See ``README.md`` next to this script for the full pipeline.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


WAKE_PHRASE = "Hey Sabrina"
DEFAULT_SAMPLE_COUNT = 4000
DEFAULT_SEED = 1337


def project_paths(script_path: Path) -> tuple[Path, Path]:
    """Return (training_dir, positives_dir) anchored to this script.

    ``training_dir`` is ``sabrina-2/tools/wake-training/``; ``positives_dir``
    is ``training_dir / "data" / "positive"``. Computed from the script's
    own location so the tool works regardless of cwd.
    """

    training_dir = script_path.resolve().parent
    positives_dir = training_dir / "data" / "positive"
    return training_dir, positives_dir


def build_command(
    *,
    phrase: str,
    output_dir: Path,
    max_samples: int,
    seed: int,
) -> list[str]:
    """Construct the ``python -m piper_sample_generator ...`` argv.

    Pure function; keeps argv assembly testable without invoking subprocess.
    """

    return [
        sys.executable,
        "-m",
        "piper_sample_generator",
        phrase,
        "--max-samples",
        str(max_samples),
        "--output-dir",
        str(output_dir),
        "--seed",
        str(seed),
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthesize positive wake-word samples for 'Hey Sabrina'.",
    )
    parser.add_argument(
        "--phrase",
        default=WAKE_PHRASE,
        help=f"Wake-word phrase to synthesize (default: {WAKE_PHRASE!r}).",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=DEFAULT_SAMPLE_COUNT,
        help=f"How many samples to generate (default: {DEFAULT_SAMPLE_COUNT}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Deterministic RNG seed (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the default `data/positive/` output directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command without invoking it; exit 0.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    _, default_positives = project_paths(Path(__file__))
    output_dir = args.output_dir if args.output_dir is not None else default_positives

    cmd = build_command(
        phrase=args.phrase,
        output_dir=output_dir,
        max_samples=args.max_samples,
        seed=args.seed,
    )

    rendered = " ".join(shlex.quote(part) for part in cmd)

    if args.dry_run:
        print(rendered)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"running: {rendered}")
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
