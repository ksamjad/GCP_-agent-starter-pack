import requests
import subprocess
import json
import os
import sys

# --- Configuration ---
PROJECT_NUM = "362440398011"  # Replace with your GCP project ID
APP_ID = "Agentspace -WalmartUS"  # Replace with your App ID
DISPLAY_NAME = "Data Analyst Agent"  # Replace with your desired display name
DESCRIPTION = "ADK agent to perform Data Analysis and Insights"  # Replace with your desired description
TOOL_DESCRIPTION = "The agent can access bigquery datasets and tables, run queries and provide insights"  # Replace with your tool description
#ADK_DEPLOYMENT_ID = "6386900318029873152"  # Replace with your ADK deployment ID
ADK_DEPLOYMENT_ID = "6414168206398717952"  # OAUTH TEsting
#AUTH_ID = "MyOAuthID_ADKBQToolsOAUTHtest"  # Replace with your authorization ID
# --- End Configuration ---

def get_gcloud_access_token():
    """
    Retrieves a Google Cloud access token using the gcloud CLI.
    """
    try:
        # Check if gcloud is installed
        subprocess.run(["gcloud", "--version"], check=True, capture_output=True, shell=True)
    except FileNotFoundError:
        print("Error: The 'gcloud' command-line tool is not found.")
        print("Please ensure it is installed and in your system's PATH.")
        return None

    try:
        token_command = ["gcloud", "auth", "print-access-token"]
        # The check=True parameter will raise an exception if the command fails
        result = subprocess.run(token_command, check=True, capture_output=True, text=True, shell=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting access token: {e.stderr.strip()}")
        return None

def create_agent():
    """
    Creates an agent using the Google Discovery Engine API.
    """
  # access_token = get_gcloud_access_token()
    access_token = "ya29.a0ATi6K2tHrBMlwp0Wbea1v2I8lUUTC_NfZK7EWA_50hbnJemUDnsjI6IZtdsvrG7BPeErKaDoYbcTcM4vDSo3YjZSO-OIjeQKHdNVJLTZeAXBSYF0b-__WwlqmI3mD3_UG0QZnzQvO35EY-n10R9A_pHPxG6iy-3J5aM2v0eyGiwEqEpMModaKL7D2mjEe37RnKDv8AEDd15aaCgYKAdoSARYSFQHGX2MillHiD4KkV15EwxYhOQHkYA0211"

    if not access_token:
        return

    url = (
        f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_NUM}/"
        f"locations/global/collections/default_collection/engines/{APP_ID}/"
        f"assistants/default_assistant/agents"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_NUM,
    }

    payload = {
        "displayName": DISPLAY_NAME,
        "description": DESCRIPTION,
        "adk_agent_definition": {
            "tool_settings": {
                "tool_description": TOOL_DESCRIPTION
            },
            "provisioned_reasoning_engine": {
                "reasoning_engine":
                    f"projects/{PROJECT_NUM}/locations/us-central1/reasoningEngines/{ADK_DEPLOYMENT_ID}"
            },
          #  "authorizations": [
          #      f"projects/{PROJECT_NUM}/locations/global/authorizations/{AUTH_ID}"
         #   ]
        }
    }

    print(f"Making POST request to: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        print("Agent created successfully!")
        print("Response:")
        print(json.dumps(response.json(), indent=2))

    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
        print(f"Response content: {response.text}")
    except requests.exceptions.ConnectionError as err:
        print(f"Error connecting to the server: {err}")
    except requests.exceptions.Timeout as err:
        print(f"The request timed out: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An unexpected error occurred: {err}")

if __name__ == "__main__":
    create_agent()
