"""Safe CSV generation from persisted, bounded AI result snapshots."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    text = str(value).replace("\x00", "")
    if text.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _json_value(value: Any, fallback: Any) -> Any:
    """Decode JSONB values returned as strings by asyncpg, without trusting shape."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return fallback
    return value


def build_message_csv(message: dict, max_rows: int = 500) -> bytes:
    raw_rows = _json_value(message.get("chart_data"), [])
    rows = raw_rows if isinstance(raw_rows, list) else []
    rows = [row for row in rows[:max(1, max_rows)] if isinstance(row, dict)]

    raw_insights = _json_value(message.get("insights"), [])
    insights = raw_insights if isinstance(raw_insights, list) else []
    insight_text = " | ".join(str(item) for item in insights if item is not None)

    raw_sources = _json_value(message.get("sources"), [])
    sources = raw_sources if isinstance(raw_sources, list) else []
    source = sources[0].get("tool", "") if sources and isinstance(sources[0], dict) else ""

    metadata_keys = ["answer", "insights", "confidence", "source", "created_at"]
    metadata = {
        "answer": sanitize_csv_value(message.get("content")),
        "insights": sanitize_csv_value(insight_text),
        "confidence": sanitize_csv_value(message.get("confidence")),
        "source": sanitize_csv_value(source),
        "created_at": sanitize_csv_value(message.get("created_at")),
    }

    if rows:
        data_keys: list[str] = []
        for row in rows:
            for key, value in row.items():
                if (
                    key not in data_keys
                    and not key.endswith("_id")
                    and (value is None or isinstance(value, (str, int, float, bool)))
                ):
                    data_keys.append(key)
                if len(data_keys) >= 12:
                    break
            if len(data_keys) >= 12:
                break
        keys = metadata_keys + data_keys
        export_rows = []
        for index, row in enumerate(rows):
            exported = {
                key: sanitize_csv_value(row.get(key)) for key in data_keys
            }
            exported.update(metadata if index == 0 else {key: "" for key in metadata_keys})
            export_rows.append(exported)
    else:
        keys = metadata_keys
        export_rows = [metadata]

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(export_rows)
    return ("\ufeff" + output.getvalue()).encode("utf-8")
