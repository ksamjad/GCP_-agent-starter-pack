import subprocess
import json
import requests
import os

# --- Configuration ---
# Replace these with your actual values
PROJECT_NUMBER = "994041294907"
LOCATION = "global"
AUTH_ID = "MyOAuthID_ADKBQToolsOAUTHtest"
CLIENT_ID = "994041294907-efj9slb2tt363vt8o97ekv215r2vei5v.apps.googleusercontent.com"
CLIENT_SECRET = "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"
AUTHORIZATION_URI = "https://accounts.google.com/o/oauth2/v2/auth?client_id=994041294907-efj9slb2tt363vt8o97ekv215r2vei5v.apps.googleusercontent.com&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fbigquery&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent"
TOKEN_URI = "https://oauth2.googleapis.com/token"

def get_access_token():
    """
    Retrieves a Google Cloud access token using the gcloud CLI.
    """
    try:
        # Check if gcloud is installed
        subprocess.run(["gcloud", "--version"], check=True, capture_output=True)
    except FileNotFoundError:
        print("Error: The 'gcloud' command-line tool is not found.")
        print("Please ensure it is installed and in your system's PATH.")
        return None

    try:
        token_command = ["gcloud", "auth", "print-access-token"]
        # The check=True parameter will raise an exception if the command fails
        result = subprocess.run(token_command, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting access token: {e.stderr.strip()}")
        return None

def create_authorization():
    """
    Sends the POST request to the Google Cloud Discovery Engine API.
    """
    access_token = get_access_token()
    if not access_token:
        return

    url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations?authorizationId={AUTH_ID}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": PROJECT_NUMBER
    }

    data = {
        "name": f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/authorizations/{AUTH_ID}",
        "serverSideOauth2": {
            "clientId": CLIENT_ID,
            "clientSecret": CLIENT_SECRET,
            "authorizationUri": AUTHORIZATION_URI,
            "tokenUri": TOKEN_URI
        }
    }
    
    print(f"Attempting to create authorization at URL: {url}")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status() # Raises a HTTPError if the response status is not successful
        print("Authorization created successfully.")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(f"Response content: {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        
if __name__ == "__main__":
    create_authorization()
