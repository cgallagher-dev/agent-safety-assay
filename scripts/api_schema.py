"""Print the JSON Schema of the dashboard API responses.

The dashboard's TypeScript types are generated from it. Regenerate both with:

    uv run python scripts/api_schema.py > frontend/src/api/schema.json
    (cd frontend && npm run gen:types)
"""

import json

from assay.server import api_schema

print(json.dumps(api_schema(), indent=2))
