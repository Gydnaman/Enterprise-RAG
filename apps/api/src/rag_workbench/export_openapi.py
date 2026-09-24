from __future__ import annotations

import json
from pathlib import Path

from rag_workbench.main import app

output = Path(__file__).parents[4] / "docs" / "api" / "openapi.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(output)
