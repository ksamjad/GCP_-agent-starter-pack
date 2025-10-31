# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deployment script for Winsights BigQuery Agent (wmt-ade-agentspace-dev)."""

import os
from pathlib import Path
from absl import app, flags
from dotenv import load_dotenv

import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# ---------------------------------------------------------------------------
# IMPORT LOCAL AGENT PACKAGE
# ---------------------------------------------------------------------------
# Your project structure is:  GCP_Agent_Starter_pack\bq_agent_app
_PACKAGE_ROOT = Path(__file__).resolve().parent / "bq_agent_app"
print(f"📦 Using package root: {_PACKAGE_ROOT}")

from bq_agent_app.agent import root_agent

# ---------------------------------------------------------------------------
# GLOBALS AND FLAGS
# ---------------------------------------------------------------------------
FLAGS = flags.FLAGS
_ENV_PREFIXES = ("BQ_AGENT_", "OAUTH_", "MS_GRAPH_", "GT_WF_")
_ENV_PASSTHROUGH = {"GOOGLE_APPLICATION_CREDENTIALS"}

flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCS bucket for staging deployments.")

flags.DEFINE_string("resource_id", None, "Vertex ReasoningEngine resource ID.")
flags.DEFINE_bool("create", False, "Creates a new deployment.")
flags.DEFINE_bool("update", False, "Updates an existing deployment.")
flags.DEFINE_bool("delete", False, "Deletes an existing deployment.")
flags.DEFINE_bool("quicktest", False, "Runs a quick test on a deployed agent.")
flags.DEFINE_string(
    "message",
    "What insights can you share today?",
    "Prompt to send when running --quicktest.",
)

flags.mark_bool_flags_as_mutual_exclusive(["create", "update", "delete", "quicktest"])


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _collect_env_vars() -> dict[str, str]:
    """Collect relevant environment variables for remote deployment."""
    env_vars: dict[str, str] = {}

    def _include(name: str) -> bool:
        return any(name.startswith(p) for p in _ENV_PREFIXES) or name in _ENV_PASSTHROUGH

    for key, val in os.environ.items():
        if _include(key) and val:
            env_vars[key] = val

    # ✅ Ensure metadata directory is available remotely
    if "BQ_AGENT_METADATA_DIR" not in env_vars:
        env_vars["BQ_AGENT_METADATA_DIR"] = str(_PACKAGE_ROOT / "metadata")

    return env_vars


def _print_env_vars(env_vars: dict[str, str]) -> None:
    """Print a sanitized preview of variables sent to remote environment."""
    if not env_vars:
        print("No environment variables detected — relying on defaults.")
        return

    print("\nPassing these environment variables to the remote agent:")
    for key in sorted(env_vars):
        value = env_vars[key]
        if len(value) > 10:
            value = value[:4] + "…" + value[-2:]
        print(f"  - {key}={value}")


# ---------------------------------------------------------------------------
# DEPLOYMENT ACTIONS
# ---------------------------------------------------------------------------
def create(env_vars: dict[str, str]) -> None:
    """Creates a new Vertex AI agent deployment."""
    print("\n=== Creating new Winsights Agent ===")
    _print_env_vars(env_vars)

    app_obj = AdkApp(agent=root_agent, enable_tracing=True, env_vars=env_vars)
    remote_agent = agent_engines.create(
        app_obj,
        requirements=str(_PACKAGE_ROOT / "requirements.txt"),
        extra_packages=[str(_PACKAGE_ROOT)],  # ✅ Upload the entire package
    )

    print("\n✅ Agent created successfully!")
    print(f"Resource name: {remote_agent.resource_name}\n")


def update(env_vars: dict[str, str], resource_id: str) -> None:
    """Updates an existing Vertex AI agent deployment."""
    print("\n=== Updating Winsights Agent ===")
    _print_env_vars(env_vars)

    app_obj = AdkApp(agent=root_agent, enable_tracing=True, env_vars=env_vars)
    agent_engines.update(
        resource_name=resource_id,
        agent_engine=app_obj,
        requirements=str(_PACKAGE_ROOT / "requirements.txt"),
        extra_packages=[str(_PACKAGE_ROOT)],
        display_name="wmt_bigquery_agent",
        description="British-flavoured Winsights BigQuery Agent for wmt-ade-agentspace-dev",
    )

    print("\n✅ Agent updated successfully!")
    print(f"Resource ID: {resource_id}\n")


def delete(resource_id: str) -> None:
    """Deletes an existing remote agent deployment."""
    print("\n=== Deleting remote agent ===")
    agent = agent_engines.get(resource_id)
    agent.delete(force=True)
    print(f"✅ Deleted remote agent: {resource_id}\n")


def quicktest(resource_id: str, message: str) -> None:
    """Runs a quick test against the deployed agent."""
    print("\n=== Running quick test ===")
    agent = agent_engines.get(resource_id)
    session = agent.create_session(user_id="samjad_ae")

    for event in agent.stream_query(user_id="samjad_ae", session_id=session["id"], message=message):
        print(event)

    print("\n✅ Quick test complete!\n")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    load_dotenv()
    env_vars = _collect_env_vars()

    project_id = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION")
    bucket = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

    print("\n=== Deployment Environment ===")
    print(f"PROJECT:  {project_id}")
    print(f"LOCATION: {location}")
    print(f"BUCKET:   {bucket}\n")

    if not project_id or not location or not bucket:
        print("❌ Missing required GOOGLE_CLOUD_* environment variables.")
        return

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=f"gs://{bucket}",
    )

    if FLAGS.create:
        create(env_vars)
    elif FLAGS.update:
        if not FLAGS.resource_id:
            print("❌ --resource_id required for --update")
            return
        update(env_vars, FLAGS.resource_id)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("❌ --resource_id required for --delete")
            return
        delete(FLAGS.resource_id)
    elif FLAGS.quicktest:
        if not FLAGS.resource_id:
            print("❌ --resource_id required for --quicktest")
            return
        quicktest(FLAGS.resource_id, FLAGS.message)
    else:
        print("⚠️  No action specified. Use one of: --create, --update, --delete, --quicktest")


if __name__ == "__main__":
    app.run(main)
