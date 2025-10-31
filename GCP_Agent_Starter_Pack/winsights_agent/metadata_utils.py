"""Metadata helpers for Winsights datasets."""

from __future__ import annotations
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Tuple

DEFAULT_METADATA_DIR = Path(os.getenv("BQ_AGENT_METADATA_DIR", Path(__file__).parent / "metadata"))

_M365_KEYWORDS = {
    "m365", "microsoft 365", "office 365", "mailbox", "outlook", "exchange",
    "teams", "sharepoint", "intune", "azure ad", "entra", "graph", "license",
    "onedrive", "ms graph", "microsoft graph",
}

_WORKFORCE_KEYWORDS = {
    "workforce", "employment", "employee", "headcount", "attrition", "turnover",
    "hiring", "recruitment", "vacancy", "vacancies", "talent", "organisation",
    "organization", "people analytics", "hr", "human resources", "labour", "labor",
}


def _normalise_identifier(value: str) -> str:
    parts = value.replace("`", "").split(".")
    return parts[-1].lower()


def _iter_metadata_files() -> Iterable[Path]:
    if not DEFAULT_METADATA_DIR.exists():
        return []
    return sorted(DEFAULT_METADATA_DIR.glob("*.json"))


@lru_cache(maxsize=1)
def _load_all_metadata() -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    for path in _iter_metadata_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        dataset_id = payload.get("dataset") or payload.get("dataset_id") or path.stem
        datasets[_normalise_identifier(dataset_id)] = payload
    return datasets


def get_all_metadata() -> dict[str, Any]:
    return _load_all_metadata().copy()


def get_dataset_metadata(dataset_id: str) -> dict[str, Any] | None:
    return _load_all_metadata().get(_normalise_identifier(dataset_id))


def _iter_table_entries(dataset_meta: dict[str, Any]) -> Iterable[Tuple[str, dict[str, Any]]]:
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
    dm = get_dataset_metadata(dataset_id)
    if not dm:
        return None
    target = _normalise_identifier(table_id)
    for tname, info in _iter_table_entries(dm):
        if tname == target:
            return info
    return None


def route_question_to_dataset(question: str) -> tuple[str | None, str]:
    text = (question or "").lower()
    m365_matches = sorted({w for w in _M365_KEYWORDS if w in text})
    wf_matches = sorted({w for w in _WORKFORCE_KEYWORDS if w in text})

    if m365_matches and not wf_matches:
        return "ms_graph", f"Matched Microsoft 365 keywords: {', '.join(m365_matches)}."
    if wf_matches and not m365_matches:
        return "gt_wf", f"Matched workforce keywords: {', '.join(wf_matches)}."
    if m365_matches and wf_matches:
        return "ms_graph", "Matched both; prioritising ms_graph by default."
    return None, "No routing keywords detected; fall back to general reasoning."


def summarise_metadata_for_prompt() -> str:
    metadata = _load_all_metadata()
    if not metadata:
        return "(No metadata files found; rely on exploratory analysis.)"

    lines: list[str] = []
    for dataset_id in sorted(metadata):
        dm = metadata[dataset_id]
        desc = dm.get("description") or dm.get("summary") or ""
        headline = f"- Dataset `{dataset_id}`"
        if desc:
            headline += f": {desc}"
        lines.append(headline)

        for tbl, info in _iter_table_entries(dm):
            tdesc = info.get("description") or info.get("summary") or ""
            rows = info.get("row_count") or info.get("rows")
            cols = info.get("columns")
            if isinstance(cols, dict):
                cols_list = list(cols.keys())[:5]
            elif isinstance(cols, list):
                cols_list = [c.get("name") if isinstance(c, dict) else c for c in cols][:5]
            else:
                cols_list = []
            detail = f"  • Table `{tbl}`"
            if tdesc:
                detail += f": {tdesc}"
            if rows:
                detail += f" (≈ {rows} rows)"
            if cols_list:
                detail += f" — key fields: {', '.join(cols_list)}"
            lines.append(detail)
    return "\n".join(lines)


def create_dashboard_plan(*, objective: str, question: str | None = None, focus_tables: list[str] | None = None) -> dict[str, Any]:
    focus_tables = focus_tables or []
    notes = [objective]
    if question:
        notes.append(f"User question: {question}")
    if focus_tables:
        notes.append(f"Tables: {', '.join(focus_tables)}")
    return {"objective": objective, "question": question, "focus_tables": focus_tables, "notes": "\n".join(notes)}
