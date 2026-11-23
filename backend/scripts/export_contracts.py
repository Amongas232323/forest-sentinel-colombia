"""Exporta los contratos entre módulos a /contracts (córranlo después de cambiar schemas).

    python scripts/export_contracts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import create_app  # noqa: E402
from sentinel_ml.contracts import CONTRACT_VERSION, PipelineResult  # noqa: E402


def main() -> None:
    out = ROOT / "contracts"
    out.mkdir(exist_ok=True)
    (out / "openapi.json").write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
    schema = TypeAdapter(PipelineResult).json_schema()
    schema["$comment"] = f"sentinel_ml PipelineResult contract v{CONTRACT_VERSION} (generated)"
    (out / "pipeline_result.schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print("contracts exported to", out)


if __name__ == "__main__":
    main()
