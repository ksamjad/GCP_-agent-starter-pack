#!/usr/bin/env python3
from __future__ import annotations

"""
Deploy the SharePoint Agent to Cloud Run using environment variables from .env.

✅ Loads .env automatically
✅ Works on Windows / macOS / Linux
✅ Detects gcloud.cmd / gcloud.exe automatically
✅ Builds and deploys to Cloud Run
✅ Optionally creates / updates Secret Manager secret (GRAPH_CLIENT_SECRET)

Expected .env entries:
  PROJECT_ID=<your GCP project ID>
  REGION=<your Cloud Run region>
  SERVICE_NAME=sharepoint-agent
  GRAPH_CLIENT_ID=...
  GRAPH_TENANT_ID=...
  GRAPH_CLIENT_SECRET=...      (optional)
  GRAPH_SCOPES=Sites.Read.All Files.Read.All
  AGENT_MODEL=gemini-2.5-flash
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv


# ---------- Utility functions ----------
def run(cmd: list[str], *, input: str | None = None):
    """Run a command with streaming output and exit on error."""
    print(f"\n>>> {' '.join(cmd)}")
    try:
        subprocess.run(cmd, input=input, text=True, check=True)
    except FileNotFoundError:
        print("❌ Command not found. Make sure gcloud is installed and in PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed (exit code {e.returncode})")
        sys.exit(e.returncode)


def resolve_gcloud() -> str:
    """Detect the gcloud CLI executable path for Windows and Unix systems."""
    # Try standard PATH
    gcloud_path = shutil.which("gcloud")
    if gcloud_path:
        return gcloud_path

    # Common Windows install locations
    candidates = [
        r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        str(Path.home() / "AppData" / "Local" / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd"),
    ]
    for path in candidates:
        if Path(path).exists():
            return path

    print("❌ Could not locate gcloud CLI. Install the Google Cloud SDK or add it to PATH.")
    sys.exit(1)


# ---------- Main deploy logic ----------
def main():
    # Load .env
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("❌ Missing .env file. Please create one with project, region, and credentials.")
        sys.exit(1)

    load_dotenv(env_path)
    print(f"✅ Loaded environment variables from {env_path}")

    # Required configs
    project = os.getenv("PROJECT_ID")
    region = os.getenv("REGION")
    service = os.getenv("SERVICE_NAME", "sharepoint-agent")
    image_tag = os.getenv("IMAGE_TAG", "latest")

    if not project or not region:
        print("❌ PROJECT_ID and REGION must be set in .env.")
        sys.exit(1)

    image = f"gcr.io/{project}/{service}:{image_tag}"

    # Locate agent code directory
    agent_dir = Path(__file__).parent / "agent"
    if not (agent_dir / "agent.py").exists():
        print("❌ Could not find ./agent/agent.py — check your folder structure.")
        sys.exit(1)

    # Find gcloud executable
    gcloud = resolve_gcloud()
    print(f"☁️  Using gcloud executable: {gcloud}")

    # ---- Step 1: Build Docker image ----
    print(f"🚧 Building Docker image: {image}")
    run([gcloud, "builds", "submit", str(agent_dir), "--tag", image, "--project", project])

    # ---- Step 2: Handle secret if provided ----
    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    secret_name = "GRAPH_CLIENT_SECRET"
    secret_binding = []

    if client_secret:
        print("🔐 Creating or updating Secret Manager secret ...")
        # Create secret if not exists
        run([
            "bash", "-c",
            f"{gcloud} secrets describe {secret_name} --project={project} "
            f"|| echo -n '{client_secret}' | {gcloud} secrets create {secret_name} "
            f"--data-file=- --project={project}"
        ])
        # Add new version
        run([
            "bash", "-c",
            f"echo -n '{client_secret}' | {gcloud} secrets versions add {secret_name} "
            f"--data-file=- --project={project}"
        ])
        secret_binding = [
            "--set-secrets",
            f"GRAPH_CLIENT_SECRET=projects/{project}/secrets/{secret_name}:latest",
        ]
    else:
        print("⚠️  No GRAPH_CLIENT_SECRET found in .env → deploying with delegated (device-code) flow.")

    # ---- Step 3: Prepare runtime environment ----
    graph_client_id = os.getenv("GRAPH_CLIENT_ID")
    graph_tenant_id = os.getenv("GRAPH_TENANT_ID")
    graph_scopes = os.getenv("GRAPH_SCOPES", "Sites.Read.All Files.Read.All")
    graph_token_cache = "/tmp/.graph_sharepoint_cache.json"
    agent_model = os.getenv("AGENT_MODEL", "gemini-2.5-flash")

    if not graph_client_id or not graph_tenant_id:
        print("❌ GRAPH_CLIENT_ID and GRAPH_TENANT_ID must be set in .env.")
        sys.exit(1)

    env_vars = ",".join([
        f"GRAPH_CLIENT_ID={graph_client_id}",
        f"GRAPH_TENANT_ID={graph_tenant_id}",
        f"GRAPH_SCOPES={graph_scopes}",
        f"GRAPH_TOKEN_CACHE={graph_token_cache}",
        f"AGENT_MODEL={agent_model}",
    ])

    # ---- Step 4: Deploy to Cloud Run ----
    print(f"🚀 Deploying {service} to Cloud Run (region: {region}) ...")
    cmd = [
        gcloud, "run", "deploy", service,
        "--image", image,
        "--region", region,
        "--platform", "managed",
        "--project", project,
        "--allow-unauthenticated",
        "--memory", "512Mi",
        "--cpu", "1",
        "--concurrency", "10",
        "--set-env-vars", env_vars,
    ]
    if secret_binding:
        cmd += secret_binding

    run(cmd)
    print("\n✅ Deployment completed successfully!")


if __name__ == "__main__":
    main()
