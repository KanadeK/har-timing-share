"""Exercise the installed CLI from a separate directory; creates only temp files."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "examples" / "demo.har"
    with tempfile.TemporaryDirectory(prefix="har-timing-share-smoke-") as temporary:
        output = Path(temporary) / "performance.html"
        subprocess.run(
            [sys.executable, "-m", "har_timing_share", str(source), "-o", str(output)],
            cwd=temporary,
            check=True,
        )
        text = output.read_text(encoding="utf-8")
        assert "SYNTHETIC_PRIVATE_MARKER" not in text
        assert "example.test" not in text
        result = subprocess.run(
            [sys.executable, "-m", "har_timing_share", str(source), "--format", "json", "-o", "-"],
            cwd=temporary,
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(result.stdout)["summary"]
        assert summary["span_ms"] == 350
        assert summary["known_decoded_body_bytes"] == 1800
        assert summary["unknown_body_sizes"] == 1
    print("Installed CLI smoke checks passed; temporary outputs removed.")


if __name__ == "__main__":
    main()
