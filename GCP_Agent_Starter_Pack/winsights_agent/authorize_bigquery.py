# authorize_bigquery.py
import os
from dotenv import load_dotenv
from google.adk.tools.bigquery import BigQueryCredentialsConfig

load_dotenv()

print("🔐 Starting interactive OAuth2 login for BigQuery…")

config = BigQueryCredentialsConfig(
    client_id=os.getenv("OAUTH_CLIENT_ID"),
    client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
)

print("✅ Authorisation complete.")
print("Credentials have been cached (usually under ~/.config/google-adk/).")
