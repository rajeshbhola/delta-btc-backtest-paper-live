from pathlib import Path
import json
import os
import tempfile


def save_json(path: str | Path, content) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".tmp_", suffix=".json", delete=False) as f:
            temporary_name = f.name
            json.dump(content, f, indent=2, allow_nan=False)
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return path
