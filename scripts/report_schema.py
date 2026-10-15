"""Print the JSON Schema of report.json, for generating the dashboard's TypeScript types.

Run with: uv run python scripts/report_schema.py > report.schema.json
"""

import json

from assay.report import Report

print(json.dumps(Report.model_json_schema(), indent=2))
