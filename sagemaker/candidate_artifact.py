"""Read the two expected files from a project training artifact."""
import json
import tarfile

MODEL = "btcusdt_direction_15m_60m.joblib"
METRICS = "btcusdt_direction_15m_60m.metrics.json"


def read_member(archive, name, max_size):
    matches = [m for m in archive if m.name.removeprefix("./") == name]
    if len(matches) != 1 or not matches[0].isfile() or not 0 < matches[0].size <= max_size:
        raise ValueError(f"Expected one regular file named {name} within the size limit")
    with archive.extractfile(matches[0]) as stream:
        return stream.read()


def read_candidate(stream):
    with tarfile.open(fileobj=stream, mode="r:gz") as archive:
        metrics = json.loads(read_member(archive, METRICS, 64 * 1024))
        if not (metrics["test_rows"] > 0 and 0.55 <= metrics["accuracy"] <= 1):
            raise ValueError("Candidate failed the chronological quality gate")
        return read_member(archive, MODEL, 32 * 1024 * 1024), metrics
