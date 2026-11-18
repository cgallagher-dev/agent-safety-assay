"""Print the labels the dashboard shows, so they match the console and the PDF.

Regenerate the dashboard's copy with:

    uv run python scripts/labels.py > frontend/src/labels.json
"""

import json

from assay.labels import as_json

print(json.dumps(as_json(), indent=2, ensure_ascii=False))
