import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


script = Path(__file__).resolve().parents[1] / "bin" / "prepare_candidate_image.py"
spec = importlib.util.spec_from_file_location("prepare_candidate_image", script)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize("accuracy", [0.54, 0.55])
def test_candidate_context_requires_passing_holdout(tmp_path, accuracy):
    artifact = tmp_path / "model.tar.gz"
    model = b"candidate model bytes"
    metrics = json.dumps({"accuracy": accuracy, "test_rows": 100}).encode()
    with tarfile.open(artifact, "w:gz") as archive:
        for name, content in [(release.MODEL, model), (release.METRICS, metrics)]:
            member = tarfile.TarInfo("./" + name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))

    output = tmp_path / "context"
    if accuracy < 0.55:
        with pytest.raises(ValueError, match="quality gate"):
            release.prepare(artifact, output)
        assert not output.exists()
    else:
        result = release.prepare(artifact, output)
        assert (output / release.MODEL).read_bytes() == model
        assert (output / "Dockerfile.lambda").is_file()
        assert result["accuracy"] == accuracy
