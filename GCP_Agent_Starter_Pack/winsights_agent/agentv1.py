from google.adk.agents.llm_agent import Agent
from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
import google.auth
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project restriction
TARGET_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")

# Credential type
CREDENTIALS_TYPE = "OAUTH2"

# Configure tool access (read-only)
tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

# Configure credentials
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

# Initialise BigQuery toolset (simplified, no project_id/config args)
bigquery_toolset = BigQueryToolset(
    credentials_config=credentials_config,
    tool_filter=[
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql",
    ]
)

# British tone + project guard
british_instruction = f"""
You are a data analysis agent that uses BigQuery tools.

🇬🇧 Always respond in **British English** — using polite, clear, and professional tone.
Use British spelling (e.g. analyse, colour, organise, optimise).
Format dates as DD Month YYYY (e.g. 31 October 2025).

**Project restriction:**
You are authorised to access only the BigQuery project **{TARGET_PROJECT_ID}**.
If the user’s query references a different project, politely refuse and respond:
"I'm terribly sorry, but I can only access datasets within the designated project {TARGET_PROJECT_ID}."

When generating SQL, always qualify tables using `{TARGET_PROJECT_ID}.dataset.table` format.
Do not attempt to read or write outside this project.
"""

# Create the agent
root_agent = Agent(
    model="gemini-2.5-flash",
    name="british_bigquery_agent",
    description="A British BigQuery agent restricted to a single project.",
    instruction=british_instruction,
    tools=[bigquery_toolset],
)

print(f"🇬🇧 British BigQuery agent initialised for project: {TARGET_PROJECT_ID}")
