"""Train the custom 'Hey Sabrina' wake-word model.

Wraps openWakeWord's automatic-model-training flow as a callable script.
Reads positives from ``data/positive/`` (produced by
``synthesize_positives.py``), points at openWakeWord's bundled
negative-features path, and writes ``output/hey_sabrina.onnx``.

After training, runs the held-out validation step and refuses to declare
success if upstream acceptance criteria are not met:

- recall on a held-out positive split must be >= ``MIN_RECALL`` (0.5).
- false-accept rate on the negative validation pool must be
  <= ``MAX_FALSE_ACCEPTS_PER_HOUR`` (0.2 / hour).

These thresholds match openWakeWord's published ``train`` defaults; the
research doc at ``research/2026-05-05-wake-word-training-pipeline.md``
flags issue #110 as a cautionary tale where validation-soft trainers
shipped a ~10% recall model. The script is designed to fail loud rather
than ship a sub-threshold artifact.

Run from the repo root in WSL2 with ``requirements-training.txt`` installed:

    python sabrina-2/tools/wake-training/train_hey_sabrina.py

If you want to keep going past a sub-threshold result for debugging:

    python sabrina-2/tools/wake-training/train_hey_sabrina.py --no-strict

See ``README.md`` next to this script for the full pipeline.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


MODEL_NAME = "hey_sabrina"
MIN_RECALL = 0.5
MAX_FALSE_ACCEPTS_PER_HOUR = 0.2


@dataclass(frozen=True)
class TrainingResult:
    """Outcome of one training run.

    Returned by ``train_model`` and consumed by ``acceptance_check``. Keeping
    the data model small + frozen makes the validation logic trivially
    testable without an actual openwakeword install.
    """

    model_path: Path
    recall: float
    false_accepts_per_hour: float


def acceptance_check(
    result: TrainingResult,
    *,
    min_recall: float = MIN_RECALL,
    max_false_accepts_per_hour: float = MAX_FALSE_ACCEPTS_PER_HOUR,
) -> tuple[bool, str]:
    """Return (ok, reason). Pure; safe to unit-test directly."""

    if result.recall < min_recall:
        return (
            False,
            f"recall {result.recall:.3f} < {min_recall:.3f} threshold "
            f"(model would miss too many real triggers)",
        )
    if result.false_accepts_per_hour > max_false_accepts_per_hour:
        return (
            False,
            f"false-accepts {result.false_accepts_per_hour:.3f}/hour > "
            f"{max_false_accepts_per_hour:.3f}/hour threshold "
            f"(model would fire on background speech)",
        )
    return True, "passes upstream acceptance criteria"


def project_paths(script_path: Path) -> dict[str, Path]:
    """Resolve all training-pipeline directories from the script's location.

    Returns a dict so callers can request specific subpaths by name without
    re-computing them. Returned dirs are not auto-created — that's the
    caller's job once it knows whether a dry-run is in effect.
    """

    training_dir = script_path.resolve().parent
    return {
        "training_dir": training_dir,
        "positives_dir": training_dir / "data" / "positive",
        "scratch_dir": training_dir / "scratch",
        "output_dir": training_dir / "output",
    }


def train_model(
    *,
    positives_dir: Path,
    scratch_dir: Path,
    output_dir: Path,
    seed: int,
) -> TrainingResult:
    """Invoke openWakeWord's training pipeline and return validation metrics.

    This function is the only place the heavy ``openwakeword.train`` path
    is touched. Tests mock this function directly to exercise the
    surrounding orchestration without an actual model train.
    """

    # Lazy import — keeps `openwakeword` off the cold path so the script
    # can `--help` and dry-run without the training extras installed.
    from openwakeword.train import train_model as upstream_train  # type: ignore[import-not-found]

    output_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    target_onnx = output_dir / f"{MODEL_NAME}.onnx"

    metrics = upstream_train(
        positive_dir=str(positives_dir),
        output_path=str(target_onnx),
        scratch_dir=str(scratch_dir),
        seed=seed,
    )
    # ``metrics`` is the upstream return shape; we depend only on the two
    # fields we validate. Using ``.get`` keeps this resilient if upstream
    # adds fields without breaking the wrapper.
    return TrainingResult(
        model_path=target_onnx,
        recall=float(metrics.get("recall", 0.0)),
        false_accepts_per_hour=float(metrics.get("false_accepts_per_hour", 0.0)),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the custom 'Hey Sabrina' openWakeWord model.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Deterministic RNG seed (default: 1337).",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help=(
            "Do not fail on sub-threshold recall / false-accept metrics. "
            "Useful for debugging; never use for shipped artifacts."
        ),
    )
    parser.add_argument(
        "--positives-dir",
        type=Path,
        default=None,
        help="Override the positives directory (default: data/positive/).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the output directory (default: output/).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    paths = project_paths(Path(__file__))
    positives_dir = args.positives_dir if args.positives_dir is not None else paths["positives_dir"]
    output_dir = args.output_dir if args.output_dir is not None else paths["output_dir"]

    if not positives_dir.exists():
        print(
            f"error: positives directory {positives_dir} does not exist; "
            "run synthesize_positives.py first.",
            file=sys.stderr,
        )
        return 2

    print(f"training {MODEL_NAME} from positives in {positives_dir}")
    result = train_model(
        positives_dir=positives_dir,
        scratch_dir=paths["scratch_dir"],
        output_dir=output_dir,
        seed=args.seed,
    )

    ok, reason = acceptance_check(result)
    print(
        f"trained: {result.model_path} "
        f"(recall={result.recall:.3f}, "
        f"false_accepts/hour={result.false_accepts_per_hour:.3f})"
    )
    print(f"acceptance: {reason}")

    if not ok and not args.no_strict:
        raise RuntimeError(
            f"trained model failed acceptance check: {reason}; "
            f"artifact at {result.model_path} should NOT be promoted."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
