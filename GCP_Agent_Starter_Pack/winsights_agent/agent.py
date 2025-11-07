"""
British BigQuery Agent (Vertex ADC Version)
-------------------------------------------
This agent uses Application Default Credentials (ADC) from the Vertex AI runtime
to securely query BigQuery in read-only mode.

This modified version includes a GCS path for query result file outputs,
which enables downloadable files for the end-user.
"""

import os
import json
import google.auth
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
from google.adk.tools.bigquery import BigQueryCredentialsConfig

# --------------------- CONFIG ---------------------
load_dotenv()

# Credential type: ADC | SERVICE_ACCOUNT | OAUTH2
CREDENTIALS_TYPE = os.getenv("CREDENTIALS_TYPE", os.getenv("BQ_AGENT_CREDENTIALS", "ADC"))
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")

# --- NEW: GCS Path for File Outputs ---
# This GCS path is the backend staging area for large query results.
# The ADK framework will automatically create secure, temporary download
# links for the user, so they *do not* see the GCS bucket.
OUTPUT_GCS_PATH = os.getenv("OUTPUT_GCS_PATH") # <-- NEW
if not OUTPUT_GCS_PATH: # <-- NEW
    print("⚠️  WARNING: OUTPUT_GCS_PATH is not set in environment variables.")
    print("   Large query results will NOT be available as downloadable files.")
    print("   To enable downloads, set: OUTPUT_GCS_PATH=gs://your-bucket/path")
# ----------------------------------------

# Read-only BigQuery mode + File Output Configuration
tool_config = BigQueryToolConfig(
    write_mode=WriteMode.BLOCKED,
    output_gcs_uri=OUTPUT_GCS_PATH  # <-- MODIFIED
)

# --------------------- AUTHENTICATION ---------------------
if CREDENTIALS_TYPE == "ADC":
    # Use Vertex-provided service account credentials automatically
    creds, _ = google.auth.default()
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
    print("🔑 Using Application Default Credentials (Vertex runtime).")

elif CREDENTIALS_TYPE == "SERVICE_ACCOUNT":
    creds, _ = google.auth.load_credentials_from_file("service_account_key.json")
    credentials_config = BigQueryCredentialsConfig(credentials=creds)
    print("🔑 Using Service Account credentials file.")

elif CREDENTIALS_TYPE == "OAUTH2":
    credentials_config = BigQueryCredentialsConfig(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
    print("🔑 Using OAuth2 credentials flow.")
else:
    raise ValueError(f"❌ Unknown CREDENTIALS_TYPE: {CREDENTIALS_TYPE}")

# --------------------- BIGQUERY TOOLSET ---------------------
bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    config=tool_config,  # <-- MODIFIED (pass the config object)
    tool_filter=[
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql",
    ],
)

# --------------------- METADATA LOADER ---------------------
def load_metadata_text():
    """Load dataset metadata context from JSON files."""
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
        return "No metadata context found."

    return "\n\n".join(metadata_context)

metadata_text = load_metadata_text()

# --------------------- AGENT INITIALIZATION ---------------------
root_agent = Agent(
    model="gemini-1.5-flash",
    name="british_bigquery_agent",
    description="A British BigQuery agent with read-only access and metadata awareness.",
    instruction=f"""
    🇬🇧 You are a British data analysis agent who uses BigQuery to answer questions about data.
    Always respond in polished British English — clear, formal, and professional.
    Use British spelling (analyse, colour, organise, optimise).
    Format dates as DD Month YYYY (e.g., 31 October 2025).

    **Core Directives**
    - Your **primary capability** is to execute SQL queries using your tools.
    - You **must not** claim you "cannot" create files. Your tools handle this for you.
    - When a query result is large, the `execute_sql` tool will automatically save it to a file and provide a download link. Your *only* job is to present this file link to the user.
    - **Never** say "I am an AI assistant and do not have the capability to create... files." This is incorrect. You DO have this capability via your tools.
    - **Never** apologize for truncation or claim the tool has a "maximum number of rows." If a result is large, you must state that the full results are available in the file you are providing.

    **Capabilities**
    - You can query BigQuery datasets the user has access to.
    - You can describe dataset schemas and field meanings using metadata.
    - You cannot modify or delete data (read-only mode).
    - If a query produces many results, you **will** provide a downloadable file.

    **Metadata Context**
    This is contextual information about key datasets:

    {metadata_text}
    """,
    tools=[bigquery_toolset],
)

print("✅ British BigQuery Agent initialised successfully (ADC mode).")
if OUTPUT_GCS_PATH: # <-- NEW
    print(f"   📤 File downloads enabled, staging to: {OUTPUT_GCS_PATH}")