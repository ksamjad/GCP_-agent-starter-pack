from google.adk.agents.llm_agent import Agent

from google.adk.tools.bigquery import BigQueryCredentialsConfig
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
from google.adk.tools.bigquery.config import WriteMode
import google.auth
import os
from dotenv import load_dotenv

load_dotenv()

# Define an appropriate credential type
CREDENTIALS_TYPE = "OAUTH2"

# Write modes define BigQuery access control of agent:
# ALLOWED: Tools will have full write capabilites.
# BLOCKED: Default mode. Effectively makes the tool read-only.
# PROTECTED: Only allows writes on temporary data for a given BigQuery session.
tool_config = BigQueryToolConfig(write_mode=WriteMode.BLOCKED)

if CREDENTIALS_TYPE == "OAUTH2":
  # Initiaze the tools to do interactive OAuth
  credentials_config = BigQueryCredentialsConfig(
     client_id=os.getenv("OAUTH_CLIENT_ID"),
     client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
  )
elif CREDENTIALS_TYPE == "SERVICE_ACCOUNT":
  # Initialize the tools to use the credentials in the service account key.
  creds, _ = google.auth.load_credentials_from_file("service_account_key.json")
  credentials_config = BigQueryCredentialsConfig(credentials=creds)
else:
  # Initialize the tools to use the application default credentials.
  application_default_credentials, _ = google.auth.default()
  credentials_config = BigQueryCredentialsConfig(
      credentials=application_default_credentials
  )

bigquery_toolset = BigQueryToolset(credentials_config=credentials_config,   tool_filter=[
'list_dataset_ids',
'get_dataset_info',
'list_table_ids',
'get_table_info',
'execute_sql',
     ])

root_agent = Agent(
   model="gemini-2.5-flash",
   name="mybigquery_agent",
   description=(
       "Agent that answers questions about BigQuery data by executing SQL queries"
   ),
   instruction=""" You are a data analysis agent with access to several BigQuery tools. Make use of those tools to answer the user's questions.

   """,
   tools=[bigquery_toolset],
)
