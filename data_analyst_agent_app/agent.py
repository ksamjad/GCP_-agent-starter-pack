"""Data analyst agent for the WMT ADE workspace."""

from __future__ import annotations

import base64
import builtins
import contextlib
import io
import os
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

        sandbox_locals.update({
            "px": px,
            "plotly_express": px,
            "go": go,
        })
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

root_agent = Agent(
    model="gemini-2.5-pro",
    name="wmt_data_analyst_agent",
    description=(
        "Analyst that explores datasets in the wmt-ade-agentspace-dev project using "
        "SQL and Python to surface insights and dashboards."
    ),
    instruction="""
You are an expert data analyst supporting the wmt-ade-agentspace-dev project.
Use the BigQuery tools for scalable SQL exploration and the run_python_analysis
function for in-memory pandas or visualization work. Always explain the
rationale behind your steps, summarize the insights you discover, and suggest or
produce visualizations when they help stakeholders understand the story.
""",
    tools=[bigquery_toolset, python_tool],
)
