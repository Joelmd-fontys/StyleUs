from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_exporter():
    script_path = ROOT / "scripts" / "contracts" / "export_taxonomy.py"
    spec = importlib.util.spec_from_file_location("export_taxonomy", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_taxonomy_export_matches_generated_file() -> None:
    exporter = _load_exporter()
    generated = ROOT / "apps" / "web" / "src" / "domain" / "generated" / "taxonomy.ts"

    def normalize(text: str) -> str:
        # Strip comments to focus on data content
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))
        # Remove all whitespace
        text = "".join(text.split())
        # Remove trailing commas inside arrays and objects to be robust against Prettier
        text = text.replace(",]", "]").replace(",}", "}")
        return text

    assert normalize(exporter.render_export()) == normalize(generated.read_text(encoding="utf-8"))
