"""
Simple British BigQuery Agent with Metadata Context
"""

from google.adk.agents.llm_agent import Agent
from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
import google.auth
import os
import json
from dotenv import load_dotenv

# --------------------- CONFIG ---------------------

load_dotenv()

CREDENTIALS_TYPE = os.getenv("CREDENTIALS_TYPE", "OAUTH2")
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# Read-only tool configuration
tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)


# --------------------- METADATA LOADER ---------------------

def load_metadata_text():
    """Load JSON summaries from metadata folder for dataset documentation context."""
    metadata_folder = os.path.join(os.path.dirname(__file__), "metadata")
    metadata_files = ["gt_wf_dataset_metadata.json", "ms_graph_dataset_metadata.json"]
    metadata_context = []

    for file_name in metadata_files:
        file_path = os.path.join(metadata_folder, file_name)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            dataset_name = file_name.replace("_dataset_metadata.json", "")
            summary = json.dumps(meta, indent=2)
            metadata_context.append(f"### Dataset: {dataset_name}\n```json\n{summary}\n```")

    if not metadata_context:
        return "No dataset metadata found."
    return "\n\n".join(metadata_context)


metadata_text = load_metadata_text()


# --------------------- AUTHORIZATION ---------------------

if CREDENTIALS_TYPE == "OAUTH2":
    credentials_config = BigQueryCredentialsConfig(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
elif CREDENTIALS_TYPE == "SERVICE_ACCOUNT":
    creds, _ = google.auth.load_credentials_from_file("service_account_key.json")
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
else:
    creds, _ = google.auth.default()
    credentials_config = BigQueryCredentialsConfig(credentials=creds)

# --------------------- TOOLSET ---------------------

bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    tool_filter=[
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql",
    ],
)

# --------------------- AGENT ---------------------

root_agent = Agent(
    model="gemini-2.5-flash",
    name="british_bigquery_agent",
    description="A British BigQuery agent with metadata context.",
    instruction=f"""
    🇬🇧 You are a British data analysis agent who uses BigQuery to answer questions about data.
    Always respond in polished British English — formal, clear, and professional.
    Use British spelling (analyse, colour, organise, optimise).
    Format dates as DD Month YYYY (e.g., 31 October 2025).
    
    **Capabilities**
    - You can use BigQuery to read data, summarise datasets, and explain schema fields.
    - You cannot modify or delete data (read-only mode).

    **Metadata Context**
    Use this metadata information as background context when explaining datasets or field meanings:
    {metadata_text}
    """,
    tools=[bigquery_toolset],
)

print("✅ British BigQuery Agent (with Metadata) initialised successfully.")
