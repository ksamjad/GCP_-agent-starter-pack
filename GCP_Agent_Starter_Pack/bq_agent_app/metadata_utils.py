"""Metadata helpers for the BigQuery agent tailored to Winsights datasets."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


_DEFAULT_METADATA_DIR = Path(
    os.getenv(
        "BQ_AGENT_METADATA_DIR",
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
    "microsoft graph",
    "ms graph",
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
    "labour",
    "labor",
}


def _normalise_identifier(value: str) -> str:
    """Case-fold identifiers and strip project prefixes for comparisons."""

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
            dataset_id = (
                path.stem.replace("_metadata", "").replace("-metadata", "")
            )
        dataset_key = _normalise_identifier(dataset_id)
        datasets[dataset_key] = payload
    return datasets


def get_all_metadata() -> dict[str, Any]:
    """Return metadata keyed by dataset identifier."""

    return _load_all_metadata().copy()


def get_dataset_metadata(dataset_id: str) -> dict[str, Any] | None:
    """Retrieve metadata for a given dataset, if present."""

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
    """Return metadata for a table within a dataset when available."""

    dataset_meta = get_dataset_metadata(dataset_id)
    if not dataset_meta:
        return None
    target = _normalise_identifier(table_id)
    for table_name, info in _iter_table_entries(dataset_meta):
        if table_name == target:
            return info
    return None


def route_question_to_dataset(question: str) -> tuple[str | None, str]:
    """Suggest the most relevant dataset for a natural-language prompt."""

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
            "Matched both keyword families; prioritising Microsoft 365 context by default.",
        )
    return None, "No routing keywords detected; fall back to general reasoning."


def summarise_metadata_for_prompt() -> str:
    """Produce a compact, human-friendly summary of available metadata."""

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

            detail = f"  • Table `{table_name}`"
            if table_desc:
                detail += f": {table_desc}"
            if row_count:
                detail += f" (≈ {row_count} rows)"
            if notable_columns:
                detail += f" — key fields: {', '.join(notable_columns)}"
            table_lines.append(detail)

        if table_lines:
            lines.extend(table_lines)

    return "\n".join(lines)


def create_dashboard_plan(
    *,
    objective: str,
    question: str | None = None,
    focus_tables: list[str] | None = None,
) -> dict[str, Any]:
    """Sketch a lightweight dashboard layout based on metadata cues."""

    focus_tables = focus_tables or []
    description_lines = [objective]
    if question:
        description_lines.append(f"User question: {question}")
    if focus_tables:
        description_lines.append(f"Suggested tables: {', '.join(focus_tables)}")

    return {
        "objective": objective,
        "question": question,
        "focus_tables": focus_tables,
        "notes": " \n".join(description_lines),
        "recommendation": "Use compose_dashboard in the Python tool to realise this plan.",
    }
