"""Prepare a Docker build context from a trusted, validated SageMaker output."""
import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

MODEL = "btcusdt_direction_15m_60m.joblib"
METRICS = "btcusdt_direction_15m_60m.metrics.json"
SOURCE = Path(__file__).resolve().parents[1] / "sagemaker"


def read_member(archive, name, max_size):
    matches = [member for member in archive if member.name.removeprefix("./") == name]
    if len(matches) != 1 or not matches[0].isfile() or not 0 < matches[0].size <= max_size:
        raise ValueError(f"Expected one regular file named {name} within the size limit")
    with archive.extractfile(matches[0]) as stream:
        return stream.read()


def prepare(artifact, output):
    with tarfile.open(artifact, "r:gz") as archive:
        metrics = json.loads(read_member(archive, METRICS, 64 * 1024))
        if not (metrics["test_rows"] > 0 and 0.55 <= metrics["accuracy"] <= 1):
            raise ValueError("Candidate failed the chronological quality gate")
        model = read_member(archive, MODEL, 32 * 1024 * 1024)

    output.mkdir()
    for filename in ("Dockerfile.lambda", "requirements.txt", "inference.py", "lambda_handler.py"):
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
