#!/usr/bin/env python3
from __future__ import annotations

"""
Deploy the SharePoint Agent to Cloud Run using environment variables from .env.

This script:
  • Loads .env for configuration
  • Builds the Docker image from ./agent/
  • Pushes it to GCR / Artifact Registry
  • Creates or updates Secret Manager secret (GRAPH_CLIENT_SECRET)
  • Deploys Cloud Run service with proper environment variables

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
import subprocess
import sys
from pathlib import Path
from shutil import which

from dotenv import load_dotenv


def run(cmd: list[str]):
    """Run a shell command with streaming output and handle errors."""
def run(cmd: list[str], *, input: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command with optional stdin forwarding and helpful errors."""

    print(f"\n>>> {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)
        completed = subprocess.run(
            cmd,
            check=check,
            text=True,
            input=input,
        )
    except FileNotFoundError as exc:
        print("❌ Failed to execute command. The executable was not found on PATH.")
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        print(f"❌ Command failed with exit code {exc.returncode}")
        raise SystemExit(exc.returncode) from exc

    return completed


def resolve_gcloud() -> str:
    """Return the path to the gcloud CLI, respecting the GCLOUD_PATH override."""

    def _maybe_with_extensions(path: Path) -> Path | None:
        """Return the first existing executable path derived from ``path``."""

        if path.is_file():
            return path

        candidates: list[Path] = []
        if path.suffix:
            candidates.extend(path.with_suffix(ext) for ext in ("", ".cmd", ".exe", ".bat"))
        else:
            candidates.append(path)
            candidates.extend(Path(f"{path}{ext}") for ext in (".cmd", ".exe", ".bat"))

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return None

    override = os.getenv("GCLOUD_PATH")
    if override:
        base = Path(override).expanduser()
        if base.is_dir():
            for name in ("gcloud", "gcloud.cmd", "gcloud.exe", "gcloud.bat"):
                candidate = base / name
                if candidate.is_file():
                    return str(candidate)
        else:
            resolved = _maybe_with_extensions(base)
            if resolved:
                return str(resolved)
        print(
            "⚠️  GCLOUD_PATH is set but no gcloud executable was found at",
            f"'{base}'.",
        )

    discovered = which("gcloud")
    if discovered:
        return discovered

    print(
        "❌ Could not find the 'gcloud' CLI. Install the Google Cloud SDK or set GCLOUD_PATH"
        " to the executable (file or containing directory)."
    )
    raise SystemExit(1)


def main():
    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("❌ Missing .env file. Please create one with project, region, and credentials.")
        sys.exit(1)

    load_dotenv(env_path)
    print(f"✅ Loaded environment from {env_path}")

    # Required config
    project = os.getenv("PROJECT_ID")
    region = os.getenv("REGION")
    service = os.getenv("SERVICE_NAME", "sharepoint-agent")
    image_tag = os.getenv("IMAGE_TAG", "latest")

    if not project or not region:
        print("❌ PROJECT_ID and REGION must be set in your .env file.")
        sys.exit(1)

    image = f"gcr.io/{project}/{service}:{image_tag}"
    agent_dir = Path(__file__).parent / "agent"

    if not (agent_dir / "agent.py").exists():
        print("❌ agent.py not found in ./agent/. Please check your structure.")
        sys.exit(1)

    # Resolve gcloud binary once
    gcloud = resolve_gcloud()

    # Build Docker image
    print(f"🚧 Building Docker image: {image}")
    GCLOUD = os.getenv("GCLOUD_PATH", "gcloud")
    run(["gcloud", "builds", "submit", str(agent_dir), "--tag", image, "--project", project])
    run([
        gcloud,
        "builds",
        "submit",
        str(agent_dir),
        "--tag",
        image,
        "--project",
        project,
    ])

    # Optional: handle client secret
    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    secret_name = "GRAPH_CLIENT_SECRET"
    secret_binding = []

    if client_secret:
        print("🔐 Creating or updating Secret Manager secret ...")
        run([
            "bash", "-c",
            f"gcloud secrets describe {secret_name} --project={project} "
            f"|| echo -n '{client_secret}' | gcloud secrets create {secret_name} "
            f"--data-file=- --project={project}"
        ])
        run([
            "bash", "-c",
            f"echo -n '{client_secret}' | "
            f"gcloud secrets versions add {secret_name} --data-file=- --project={project}"
        ])

        describe = run(
            [
                gcloud,
                "secrets",
                "describe",
                secret_name,
                "--project",
                project,
            ],
            check=False,
        )

        if describe.returncode != 0:
            run(
                [
                    gcloud,
                    "secrets",
                    "create",
                    secret_name,
                    "--project",
                    project,
                    "--data-file=-",
                ],
                input=client_secret,
            )

        run(
            [
                gcloud,
                "secrets",
                "versions",
                "add",
                secret_name,
                "--project",
                project,
                "--data-file=-",
            ],
            input=client_secret,
        )
        secret_binding = [
            "--set-secrets",
            f"GRAPH_CLIENT_SECRET=projects/{project}/secrets/{secret_name}:latest",
        ]
    else:
        print("⚠️  No GRAPH_CLIENT_SECRET found in .env → deploying with delegated (device-code) flow.")

    # Required runtime vars
    graph_client_id = os.getenv("GRAPH_CLIENT_ID")
    graph_tenant_id = os.getenv("GRAPH_TENANT_ID")
    graph_scopes = os.getenv("GRAPH_SCOPES", "Sites.Read.All Files.Read.All")
    graph_token_cache = "/tmp/.graph_sharepoint_cache.json"

    if not graph_client_id or not graph_tenant_id:
        print("❌ GRAPH_CLIENT_ID and GRAPH_TENANT_ID must be defined in .env.")
        sys.exit(1)

    env_vars = ",".join([
        f"GRAPH_CLIENT_ID={graph_client_id}",
        f"GRAPH_TENANT_ID={graph_tenant_id}",
        f"GRAPH_SCOPES={graph_scopes}",
        f"GRAPH_TOKEN_CACHE={graph_token_cache}",
        f"AGENT_MODEL={os.getenv('AGENT_MODEL', 'gemini-2.5-flash')}",
    ])

    print(f"🚀 Deploying {service} to Cloud Run in {region} ...")
    cmd = [
        "gcloud", "run", "deploy", service,
        gcloud,
        "run",
        "deploy",
        service,
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
    print("\n✅ Deployment complete!")


if __name__ == "__main__":
    main()