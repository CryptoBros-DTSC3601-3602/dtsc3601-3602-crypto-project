"""Prepare a Docker build context from a trusted, validated SageMaker output."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "sagemaker"
sys.path.insert(0, str(SOURCE))
from candidate_artifact import MODEL, METRICS, read_candidate


def prepare(artifact, output):
    with artifact.open("rb") as stream:
        model, metrics = read_candidate(stream)

    output.mkdir()
    for filename in ("Dockerfile.lambda", "requirements.txt", "inference.py", "lambda_handler.py", "candidate_artifact.py"):
        shutil.copyfile(SOURCE / filename, output / filename)
    (output / MODEL).write_bytes(model)
    return {
        "candidate_sha256": hashlib.sha256(model).hexdigest(),
        "accuracy": metrics["accuracy"],
        "test_rows": metrics["test_rows"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="model.tar.gz from a validated training run")
    parser.add_argument("output", type=Path, help="New directory for the candidate image context")
    args = parser.parse_args()
    print(json.dumps(prepare(args.artifact, args.output), indent=2))


if __name__ == "__main__":
    main()
