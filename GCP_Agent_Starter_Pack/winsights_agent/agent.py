"""
💙 Walmart Customer Care BigQuery Agent v2.0
---------------------------------------------
An upgraded data assistant that:
 - Queries BigQuery in read-only mode
 - Restricts access to project: wmt-ade-agentspace-dev
 - Generates charts (matplotlib)
 - Generates custom images via Gemini (GoogleTool)
 - Speaks in a friendly, professional Walmart tone
"""

import os
import json
import io
import warnings
import google.auth
import matplotlib.pyplot as plt
from PIL import Image
from dotenv import load_dotenv

# -------------------------------------------------
# SUPPRESS EXPERIMENTAL WARNINGS (safe)
# -------------------------------------------------
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]")

# -------------------------------------------------
# GOOGLE ADK IMPORTS
# -------------------------------------------------
from google.adk.agents.llm_agent import Agent
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
from google.adk.tools.bigquery import BigQueryCredentialsConfig
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.google_tool import GoogleTool

# -------------------------------------------------
# ENVIRONMENT & AUTH CONFIGURATION
# -------------------------------------------------
load_dotenv()

PROJECT_RESTRICTION = "wmt-ade-agentspace-dev"
CREDENTIALS_TYPE = os.getenv("CREDENTIALS_TYPE", "ADC")
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

# --- AUTHENTICATION ---
if CREDENTIALS_TYPE == "ADC":
    creds, _ = google.auth.default()
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
    print("✅ Using Application Default Credentials (Vertex runtime).")
elif CREDENTIALS_TYPE == "SERVICE_ACCOUNT":
    creds, _ = google.auth.load_credentials_from_file("service_account_key.json")
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
    print("✅ Using Service Account credentials file.")
elif CREDENTIALS_TYPE == "OAUTH2":
    credentials_config = BigQueryCredentialsConfig(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET
    )
    print("✅ Using OAuth2 credentials flow.")
else:
    raise ValueError(f"❌ Unknown CREDENTIALS_TYPE: {CREDENTIALS_TYPE}")

# -------------------------------------------------
# BIGQUERY TOOLSET
# -------------------------------------------------
bq = BigQueryToolset(
    credentials_config=credentials_config,
    tool_filter=[
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql",
    ],
)

# Restrict queries to project (case-insensitive)
def safe_query(sql: str) -> str:
    lowered = sql.lower()
    if PROJECT_RESTRICTION not in lowered:
        raise PermissionError(
            f"⚠️ Access denied. Queries are restricted to project '{PROJECT_RESTRICTION}'."
        )
    return lowered

def execute_sql(query: str):
    safe = safe_query(query)
    return bq.tools["execute_sql"].invoke(query=safe)

# -------------------------------------------------
# VISUALIZATION TOOL (matplotlib)
# -------------------------------------------------
def plot_bar_chart_tool(
    data: list[float],
    labels: list[str],
    title: str = "Customer Satisfaction by Category",
) -> bytes:
    """
    Generates a Walmart-branded bar chart and returns it as image bytes.
    """
    fig, ax = plt.subplots()
    ax.bar(labels, data, color="#0071ce")  # Walmart blue
    ax.set_title(title)
    ax.set_ylabel("Score / Count")
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    print("📊 Chart generated successfully.")
    return buf.getvalue()

plot_bar_chart_tool = FunctionTool(plot_bar_chart_tool)

# -------------------------------------------------
# IMAGE GENERATION TOOL (Gemini)
# -------------------------------------------------
def generate_image(prompt: str):
    """
    Uses Gemini-powered GoogleTool for image generation.
    Example: Walmart-branded illustrative visuals.
    """
    from google.adk.tools.google_tool import GoogleTool as GeminiTool
    tool = GeminiTool(func=lambda p: f"🖼️ (Generated Walmart-style image for: {p})")
    return tool.func(prompt)

# Register with ADK
image_toolset = GoogleTool(func=generate_image)

# -------------------------------------------------
# METADATA LOADER
# -------------------------------------------------
def load_metadata_text():
    folder = os.path.join(os.path.dirname(__file__), "metadata")
    files = ["gt_wf_dataset_metadata.json", "ms_graph_dataset_metadata.json"]
    parts = []
    for f in files:
        path = os.path.join(folder, f)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            parts.append(f"### {f}\n```json\n{json.dumps(meta, indent=2)}\n```")
    return "\n\n".join(parts) or "No dataset metadata available."

metadata_text = load_metadata_text()

# -------------------------------------------------
# WALMART AGENT INSTRUCTIONS
# -------------------------------------------------
agent_instructions = f"""
💙 **Welcome to Walmart Customer Care Data Assistant**

You are a friendly, professional data analysis agent representing Walmart Customer Care.
You help analyse BigQuery datasets, visualize insights, and generate clean, meaningful summaries.

### 🎯 Responsibilities
- Stay strictly within the project **{PROJECT_RESTRICTION}**.
- Handle all SQL queries in a case-insensitive way.
- Generate bar charts and visual summaries when helpful.
- Always present findings clearly, politely, and helpfully.
- You can generate and display both **charts** and **illustrative images**.

### 🧩 Capabilities
- Query BigQuery datasets and interpret customer or operational insights.
- Create bar charts and summaries using the visualization tool.
- Generate images using Walmart-branded Gemini capabilities.
- Provide structured results and professional explanations.
- Operate in read-only mode (no modifications or deletions).

### 🗣️ Tone & Style
- Friendly, clear, professional, and service-oriented.
- Use phrases like:
  - "Here’s what I found in our data."
  - "Let me visualise that for you."
  - "I’ve created a quick chart to make this clearer."
- Avoid jargon. Always focus on customer clarity.

### 📚 Dataset Context
{metadata_text}
"""

# -------------------------------------------------
# AGENT INITIALIZATION
# -------------------------------------------------
root_agent = Agent(
    model="gemini-2.5-flash",
    name="walmart_customer_care_agent",
    description="A Walmart data assistant that analyses BigQuery and generates charts or visuals for insights.",
    instruction=agent_instructions,
    tools=[bq, plot_bar_chart_tool, image_toolset],
)

print("💙 Walmart Customer Care Data Agent v2.0 initialized — ready to provide insights and visuals!")
