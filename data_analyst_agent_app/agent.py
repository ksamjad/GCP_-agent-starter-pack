"""Data analyst agent for the WMT ADE workspace."""

from __future__ import annotations

import base64
import builtins
import contextlib
import io
import os
import textwrap
import traceback
from typing import Any

import google.auth
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

try:
    from data_analyst_agent_app.metadata_utils import (
        create_dashboard_plan,
        get_dataset_metadata,
        get_table_metadata,
        route_question_to_dataset,
        summarise_metadata_for_prompt,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback for script execution
    from metadata_utils import (
        create_dashboard_plan,
        get_dataset_metadata,
        get_table_metadata,
        route_question_to_dataset,
        summarise_metadata_for_prompt,
    )
from data_analyst_agent_app.metadata_utils import (
    create_dashboard_plan,
    get_dataset_metadata,
    get_table_metadata,
    route_question_to_dataset,
    summarise_metadata_for_prompt,
)

load_dotenv()

CREDENTIALS_TYPE = os.getenv("CREDENTIALS_TYPE", "ADC").upper()
DEFAULT_PROJECT_ID = os.getenv("DATA_ANALYST_PROJECT", "wmt-ade-agentspace-dev")
DEFAULT_LOCATION = os.getenv("BIGQUERY_LOCATION", "us")


def _build_safe_globals() -> dict[str, Any]:
    """Construct a restricted globals dictionary for executing Python code."""

    allowed_builtins = {
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "pow",
        "print",
        "range",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    }
    safe_builtins = {name: getattr(builtins, name) for name in allowed_builtins}
    return {"__builtins__": safe_builtins}


def run_python_analysis(code: str) -> dict[str, Any]:
    """Execute ad-hoc Python for data exploration and dashboard creation.

    The code is executed inside a sandboxed environment that exposes popular
    data-analysis libraries. To share results with the user, assign any final
    table to a variable named ``result``. Matplotlib figures that remain open
    after execution are captured and returned as base64-encoded PNG payloads so
    the caller can render dashboards or charts.

    Args:
        code: The Python code to execute. Prefer pure functions and declarative
            analysis steps. The helper variables ``pd`` (pandas), ``np``
            (NumPy), ``plt`` (Matplotlib) and ``px`` (Plotly Express, when
            installed) are available by default.

    Returns:
        A dictionary containing stdout, optional ``result`` payloads, and any
        generated figures.
    """

    safe_globals = _build_safe_globals()
    sandbox_locals: dict[str, Any] = {
        "pd": pd,
        "pandas": pd,
        "np": np,
        "numpy": np,
        "plt": plt,
    }

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        sandbox_locals.update({
            "px": px,
            "plotly_express": px,
            "go": go,
            "plotly_graph_objects": go,
        })

        def compose_dashboard(
            charts: list[dict[str, Any]],
            *,
            title: str | None = None,
            rows: int | None = None,
            cols: int | None = None,
            shared_x: bool = False,
            shared_y: bool = False,
        ) -> "go.Figure":
            """Create a Plotly dashboard from simple chart specifications.

            Each chart specification should include a ``type`` that maps to a
            ``plotly.express`` function (for example ``bar`` or ``line``), the
            ``data`` to plot (either a pandas DataFrame or a mapping compatible
            with ``pd.DataFrame``) and optional ``params`` with keyword
            arguments passed to the plotting function. Custom placement can be
            controlled with ``row`` and ``col`` indices.
            """

            if not charts:
                raise ValueError("Please provide at least one chart specification.")

            resolved_rows = rows or len(charts)
            resolved_cols = cols or 1
            subplot_titles = [chart.get("title") for chart in charts]
            figure = make_subplots(
                rows=resolved_rows,
                cols=resolved_cols,
                subplot_titles=subplot_titles if any(subplot_titles) else None,
                shared_xaxes=shared_x,
                shared_yaxes=shared_y,
            )

            for index, chart in enumerate(charts):
                chart_type = chart.get("type", "bar")
                plot_func = getattr(px, chart_type, None)
                if plot_func is None:
                    raise ValueError(f"Unknown chart type '{chart_type}'.")

                data = chart.get("data")
                if data is None:
                    raise ValueError("Each chart specification requires a 'data' value.")
                if isinstance(data, pd.DataFrame):
                    frame = data
                else:
                    frame = pd.DataFrame(data)

                params = dict(chart.get("params", {}))
                params.setdefault("data_frame", frame)
                chart_figure = plot_func(**params)

                row = chart.get("row") or index // resolved_cols + 1
                col = chart.get("col") or index % resolved_cols + 1
                for trace in chart_figure.data:
                    figure.add_trace(trace, row=row, col=col)

                xaxis = chart_figure.layout.xaxis
                yaxis = chart_figure.layout.yaxis
                figure.update_xaxes(xaxis, row=row, col=col)
                figure.update_yaxes(yaxis, row=row, col=col)

            if title:
                figure.update_layout(title=title)

            return figure

        sandbox_locals["compose_dashboard"] = compose_dashboard
    except Exception:  # pragma: no cover - optional dependency
        pass

    stdout_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buffer):
            exec(compile(code, "<data_analyst_python_tool>", "exec"), safe_globals, sandbox_locals)  # noqa: S102
    except Exception:
        return {
            "stdout": stdout_buffer.getvalue(),
            "error": traceback.format_exc(),
        }

    figures: list[str] = []
    for figure_number in plt.get_fignums():
        figure = plt.figure(figure_number)
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        figures.append(base64.b64encode(buffer.read()).decode("utf-8"))
    plt.close("all")

    payload: dict[str, Any] = {"stdout": stdout_buffer.getvalue()}
    if "result" in sandbox_locals:
        result_obj = sandbox_locals["result"]
        if isinstance(result_obj, pd.DataFrame):
            payload["result"] = {
                "type": "dataframe",
                "columns": list(result_obj.columns),
                "records": result_obj.to_dict(orient="records"),
            }
        else:
            payload["result"] = repr(result_obj)

    if figures:
        payload["figures"] = figures

    return payload


tool_config = BigQueryToolConfig(
    write_mode=WriteMode.BLOCKED,
    compute_project_id=DEFAULT_PROJECT_ID,
    location=DEFAULT_LOCATION,
    application_name="wmt-data-analyst-agent",
    max_query_result_rows=5000,
)

if CREDENTIALS_TYPE == "OAUTH2":
    credentials_config = BigQueryCredentialsConfig(
        client_id=os.getenv("OAUTH_CLIENT_ID"),
        client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
    )
elif CREDENTIALS_TYPE == "SERVICE_ACCOUNT":
    creds, _ = google.auth.load_credentials_from_file("service_account_key.json")
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
else:
    application_default_credentials, _ = google.auth.default()
    credentials_config = BigQueryCredentialsConfig(
        credentials=application_default_credentials
    )

bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    bigquery_tool_config=tool_config,
    tool_filter=[
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql",
    ],
)

python_tool = FunctionTool(func=run_python_analysis)


def fetch_metadata(dataset_id: str, table_id: str | None = None) -> dict[str, Any]:
    """Return dataset or table metadata to guide analysis steps."""

    dataset_meta = get_dataset_metadata(dataset_id)
    if dataset_meta is None:
        raise ValueError(f"No metadata available for dataset '{dataset_id}'.")
    if table_id:
        table_meta = get_table_metadata(dataset_id, table_id)
        if table_meta is None:
            raise ValueError(
                f"No metadata available for table '{table_id}' in dataset '{dataset_id}'."
            )
        return {"dataset": dataset_id, "table": table_id, "metadata": table_meta}
    return {"dataset": dataset_id, "metadata": dataset_meta}


def recommend_dataset(question: str) -> dict[str, Any]:
    """Suggest the most relevant dataset for an incoming user query."""

    dataset_id, reason = route_question_to_dataset(question)
    return {"dataset": dataset_id, "reason": reason}


def plan_dashboard(
    objective: str,
    question: str | None = None,
    focus_tables: list[str] | None = None,
) -> dict[str, Any]:
    """Draft a dashboard plan rooted in curated metadata."""

    return create_dashboard_plan(objective=objective, question=question, focus_tables=focus_tables)


metadata_tool = FunctionTool(func=fetch_metadata)
dataset_router_tool = FunctionTool(func=recommend_dataset)
dashboard_planner_tool = FunctionTool(func=plan_dashboard)


_METADATA_PROMPT = summarise_metadata_for_prompt()

_BASE_INSTRUCTION = f"""
You are a meticulous British data analyst supporting the `{DEFAULT_PROJECT_ID}`
BigQuery project. Respond in polished British English with a confident yet
collegial tone.

Before issuing SQL, consult the curated metadata via the provided tools to
confirm relevant tables, columns, and row counts. Give preference to the
``ms_graph`` dataset for Microsoft 365, mailbox, or collaboration tooling
questions, and pivot to ``gt_wf`` when analysing workforce, employment,
attrition, or hiring matters. When metadata is inconclusive, call the
``recommend_dataset`` tool to document your routing decision.

When crafting visuals, consider combining multiple related charts into a
dashboard using the ``compose_dashboard`` helper inside ``run_python_analysis``
or the ``plan_dashboard`` function tool to sketch a layout before rendering
with Python. Always narrate your analytical steps, reference the metadata
you relied upon, and explain how stakeholders might interpret the results.

Dataset metadata overview:
{textwrap.indent(_METADATA_PROMPT, '  ')}
"""

root_agent = Agent(
    model="gemini-2.5-pro",
    name="wmt_data_analyst_agent",
    description=(
        "British-flavoured analyst for the "
        f"{DEFAULT_PROJECT_ID} BigQuery project with rich metadata awareness."
    ),
    instruction=_BASE_INSTRUCTION,
    tools=[
        dataset_router_tool,
        metadata_tool,
        dashboard_planner_tool,
        bigquery_toolset,
        python_tool,
    ],
)
