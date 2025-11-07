import requests
import subprocess
import json
import os
import sys

# --- Configuration ---
PROJECT_NUM = "362440398011"  # Replace with your GCP project ID
APP_ID = "agentspace-walmartus_1754500138149"  # Replace with your App ID
DISPLAY_NAME = "Data Analyst + Visualizer v1.2"  # Replace with your desired display name
DESCRIPTION = "British Agent to perform Data Analysis and Insights"  # Replace with your desired description
TOOL_DESCRIPTION = "The agent can access bigquery datasets and tables, run queries and provide insights+output files"  # Replace with your tool description
# ADK_DEPLOYMENT_ID = "6386900318029873152"  # Replace with your ADK deployment ID
ADK_DEPLOYMENT_ID = "6310119222039019520"  # OAUTH TEsting
LOCATION = "us"  # Define the location variable
# AUTH_ID = "MyOAuthID_ADKBQToolsOAUTHtest"  # Replace with your authorization ID
# --- End Configuration ---

def get_gcloud_access_token():
    """
    Retrieves a Google Cloud access token using the gcloud CLI.
    """
    try:
        # Check if gcloud is installed
        # Using shell=True can be a security risk if command components are from untrusted input.
        # It's generally safer to pass arguments as a list if not using shell features.
        # However, for simple commands like `gcloud --version`, it's often fine.
        subprocess.run(["gcloud", "--version"], check=True, capture_output=True, text=True, shell=sys.platform == 'win32') # Use shell=True on Windows if needed
    except FileNotFoundError:
        print("Error: The 'gcloud' command-line tool is not found.")
        print("Please ensure it is installed and in your system's PATH.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error verifying gcloud installation: {e.stderr.strip()}")
        return None

    try:
        token_command = ["gcloud", "auth", "print-access-token"]
        # Using text=True for cleaner output handling
        result = subprocess.run(token_command, check=True, capture_output=True, text=True, shell=sys.platform == 'win32') # Use shell=True on Windows if needed
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting access token: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while getting the token: {e}")
        return None


def create_agent():
    """
    Creates an agent using the Google Discovery Engine API.
    """
    access_token = get_gcloud_access_token()
    # Hardcoded token for testing - comment out get_gcloud_access_token() call above if using this
    #access_token = "ya29.a0ATi6K2t1EGnZnuYv7A0U_ZcgEyc36D6q7yG2_cMfqZQhpNvWrrrVMY7C1RKkkSpve65_YQDhw6lZndy5uvoduMCN3HSxJU2z4wB6l8EDMYsw4WUsW5cbWiun93uk3x0JTz1Kf-aWKJUUhm-NeHk9rKx203HF-zbOCWtj78C4OwCo_xE720Sf9_V3mbIh51t0EdRGQeDSRMYOaCgYKAe8SARYSFQHGX2MiuvvmWa00fQyJhcja9LakRA0211"

    if not access_token:
        print("Failed to obtain access token. Exiting.")
        return

    # *** Use the regional endpoint ***
    api_endpoint = f"https://us-discoveryengine.googleapis.com"

    url = (
        f"{api_endpoint}/v1alpha/projects/{PROJECT_NUM}/"
        f"locations/{LOCATION}/collections/default_collection/engines/{APP_ID}/"
        f"assistants/default_assistant/agents"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_NUM, # Ensure this header is needed and correct for your API call context
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
           # "authorizations": [
           #      f"projects/{PROJECT_NUM}/locations/global/authorizations/{AUTH_ID}" # Note: Authorizations might still be global
           # ]
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
        # Attempt to print JSON error details if available
        try:
            error_details = err.response.json()
            print(f"Error details: {json.dumps(error_details, indent=2)}")
        except json.JSONDecodeError:
            print(f"Response content (non-JSON): {err.response.text}")
    except requests.exceptions.ConnectionError as err:
        print(f"Error connecting to the server: {err}")
    except requests.exceptions.Timeout as err:
        print(f"The request timed out: {err}")
    except requests.exceptions.RequestException as err:
        print(f"An unexpected error occurred: {err}")

if __name__ == "__main__":
    create_agent()
