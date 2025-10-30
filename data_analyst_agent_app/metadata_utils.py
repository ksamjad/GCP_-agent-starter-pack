"""Utilities for loading dataset metadata and guiding analysis routing.

The data analyst agent can consult rich metadata supplied as JSON files to
answer exploratory questions without repeatedly scanning BigQuery tables.
The helper functions in this module load those files, expose convenient
lookups, and provide lightweight heuristics for routing incoming requests to
the correct dataset.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


_DEFAULT_METADATA_DIR = Path(
    os.getenv(
        "DATA_ANALYST_METADATA_DIR",
        Path(__file__).resolve().parent / "metadata",
    )
)

_M365_KEYWORDS = {
    "m365",
    "microsoft 365",
    "office 365",
    "mailbox",
    "outlook",
    "exchange",
    "teams",
    "sharepoint",
    "intune",
    "azure ad",
    "entra",
    "graph",
    "license",
    "licence",
    "onedrive",
    "power platform",
}

_WORKFORCE_KEYWORDS = {
    "workforce",
    "employment",
    "employee",
    "headcount",
    "attrition",
    "turnover",
    "hiring",
    "recruitment",
    "vacancy",
    "vacancies",
    "talent",
    "organisation",
    "organization",
    "people analytics",
    "hr",
    "human resources",
}

_NUMERIC_TYPES = {
    "int64",
    "int32",
    "integer",
    "float64",
    "float32",
    "float",
    "numeric",
    "bignumeric",
    "decimal",
    "number",
}


def _normalise_identifier(value: str) -> str:
    """Return a case-folded identifier without project or dataset prefixes."""

    parts = value.replace("`", "").split(".")
    return parts[-1].lower()


def _iter_metadata_files() -> Iterable[Path]:
    if not _DEFAULT_METADATA_DIR.exists():
        return []
    return sorted(_DEFAULT_METADATA_DIR.glob("*.json"))


@lru_cache(maxsize=1)
def _load_all_metadata() -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    for path in _iter_metadata_files():
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        dataset_id = payload.get("dataset") or payload.get("dataset_id")
        if not isinstance(dataset_id, str):
            dataset_id = path.stem.replace("_metadata", "").replace("-metadata", "")
        dataset_key = _normalise_identifier(dataset_id)
        datasets[dataset_key] = payload
    return datasets


def get_all_metadata() -> dict[str, Any]:
    """Return the metadata for all datasets keyed by dataset ID."""

    return _load_all_metadata().copy()


def get_dataset_metadata(dataset_id: str) -> dict[str, Any] | None:
    """Look up metadata for a specific dataset."""

    return _load_all_metadata().get(_normalise_identifier(dataset_id))


def _iter_table_entries(dataset_meta: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    tables = dataset_meta.get("tables")
    if isinstance(tables, dict):
        for name, info in tables.items():
            if isinstance(info, dict):
                yield _normalise_identifier(str(name)), info
    elif isinstance(tables, list):
        for entry in tables:
            if not isinstance(entry, dict):
                continue
            name = entry.get("table") or entry.get("table_id") or entry.get("name")
            if isinstance(name, str):
                yield _normalise_identifier(name), entry


def get_table_metadata(dataset_id: str, table_id: str) -> dict[str, Any] | None:
    """Return metadata for a specific table within a dataset, if available."""

    dataset_meta = get_dataset_metadata(dataset_id)
    if not dataset_meta:
        return None
    target = _normalise_identifier(table_id)
    for table_name, info in _iter_table_entries(dataset_meta):
        if table_name == target:
            return info
    return None


def route_question_to_dataset(question: str) -> tuple[str | None, str]:
    """Choose the most relevant dataset for a natural-language question."""

    text = question.lower()
    m365_matches = sorted({word for word in _M365_KEYWORDS if word in text})
    wf_matches = sorted({word for word in _WORKFORCE_KEYWORDS if word in text})

    if m365_matches and not wf_matches:
        return "ms_graph", f"Matched Microsoft 365 keywords: {', '.join(m365_matches)}."
    if wf_matches and not m365_matches:
        return "gt_wf", f"Matched workforce keywords: {', '.join(wf_matches)}."
    if m365_matches and wf_matches:
        return (
            "ms_graph",
            "Matched both keyword groups; prioritising Microsoft 365 context by default.",
        )
    return None, "No routing keywords detected; fall back to general reasoning."


def summarise_metadata_for_prompt() -> str:
    """Create a compact, human-readable summary of all dataset metadata."""

    metadata = _load_all_metadata()
    if not metadata:
        return "(No metadata files were found; rely on exploratory analysis.)"

    lines: list[str] = []
    for dataset_id in sorted(metadata):
        dataset_meta = metadata[dataset_id]
        description = dataset_meta.get("description") or dataset_meta.get("summary") or ""
        headline = f"- Dataset `{dataset_id}`"
        if description:
            headline += f": {description}"
        lines.append(headline)
        table_lines: list[str] = []
        for table_name, info in _iter_table_entries(dataset_meta):
            table_desc = info.get("description") or info.get("summary") or ""
            row_count = info.get("row_count") or info.get("rows")
            column_info = info.get("columns")
            if isinstance(column_info, dict):
                notable_columns = list(column_info.keys())[:5]
            elif isinstance(column_info, list):
                notable_columns = []
                for column in column_info:
                    if isinstance(column, dict):
                        name = column.get("name") or column.get("column")
                        if name:
                            notable_columns.append(name)
                    elif isinstance(column, str):
                        notable_columns.append(column)
                    if len(notable_columns) >= 5:
                        break
            else:
                notable_columns = []
            column_text = (
                f" Key fields: {', '.join(notable_columns)}."
                if notable_columns
                else ""
            )
            row_text = f" Rows: {row_count}." if row_count else ""
            detail = f"    • {table_name}: {table_desc}{row_text}{column_text}".rstrip()
            table_lines.append(detail)
        if table_lines:
            lines.extend(table_lines)
    return "\n".join(lines)


def create_dashboard_plan(
    objective: str,
    question: str | None = None,
    focus_tables: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a lightweight dashboard plan using available metadata."""

    dataset_id, reason = route_question_to_dataset(question or objective)
    dataset_meta = get_dataset_metadata(dataset_id) if dataset_id else None
    tables: list[dict[str, Any]] = []
    if dataset_meta:
        table_entries = list(_iter_table_entries(dataset_meta))
        requested = [
            _normalise_identifier(name)
            for name in focus_tables or []
        ]
        for name, info in table_entries:
            if requested and name not in requested:
                continue
            entry = {
                "table": name,
                "description": info.get("description") or info.get("summary"),
            }
            column_info = info.get("columns")
            numeric_columns: list[str] = []
            categorical_columns: list[str] = []
            if isinstance(column_info, dict):
                for column_name, column_meta in column_info.items():
                    if not isinstance(column_meta, dict):
                        continue
                    dtype = str(column_meta.get("type") or column_meta.get("data_type") or "").lower()
                    if dtype in _NUMERIC_TYPES:
                        numeric_columns.append(column_name)
                    else:
                        categorical_columns.append(column_name)
            elif isinstance(column_info, list):
                for column_meta in column_info:
                    if isinstance(column_meta, dict):
                        name = column_meta.get("name") or column_meta.get("column")
                        dtype = str(column_meta.get("type") or column_meta.get("data_type") or "").lower()
                        if not name:
                            continue
                        if dtype in _NUMERIC_TYPES:
                            numeric_columns.append(name)
                        else:
                            categorical_columns.append(name)
                    elif isinstance(column_meta, str):
                        categorical_columns.append(column_meta)
            entry["numeric_columns"] = numeric_columns
            entry["categorical_columns"] = categorical_columns
            tables.append(entry)
            if not requested and len(tables) >= 4:
                break

    visualisations: list[dict[str, Any]] = []
    for table in tables:
        if table["numeric_columns"]:
            metric = table["numeric_columns"][0]
            dimension = table["categorical_columns"][0] if table["categorical_columns"] else None
            suggestion = {
                "table": table["table"],
                "chart_type": "bar" if dimension else "indicator",
                "metric": metric,
                "dimension": dimension,
                "description": (
                    f"Aggregate {metric} by {dimension}"
                    if dimension
                    else f"Track {metric} over time or as a KPI"
                ),
            }
            visualisations.append(suggestion)

    return {
        "objective": objective,
        "question": question,
        "recommended_dataset": dataset_id,
        "routing_reason": reason,
        "recommended_tables": tables,
        "visualisations": visualisations,
    }


__all__ = [
    "create_dashboard_plan",
    "get_all_metadata",
    "get_dataset_metadata",
    "get_table_metadata",
    "route_question_to_dataset",
    "summarise_metadata_for_prompt",
]

