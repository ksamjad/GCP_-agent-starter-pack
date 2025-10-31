#!/usr/bin/env python3
# Copyright 2025
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

"""
Deployment script for the Winsights BigQuery Agent.

Usage:
  python -m bq_agent_app.deploy --create
  python deploy.py --update --resource_id=<resource>
  python deploy.py --quicktest --resource_id=<resource>
"""

import os
from pathlib import Path
from absl import app, flags
from dotenv import load_dotenv

import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# ✅ Import from package
from bq_agent_app.agent import root_agent


# -------------------------------------------------------------------
# FLAGS AND GLOBALS
# -------------------------------------------------------------------
FLAGS = flags.FLAGS
_PACKAGE_ROOT = Path(__file__).resolve().parent / "bq_agent_app"
_ENV_PREFIXES = ("BQ_AGENT_", "OAUTH_", "MS_GRAPH_", "GT_WF_")
_ENV_PASSTHROUGH = {"GOOGLE_APPLICATION_CREDENTIALS"}

flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCS staging bucket for deployment.")
flags.DEFINE_string("resource_id", None, "Existing ReasoningEngine resource ID.")
flags.DEFINE_bool("create", False, "Create a new agent deployment.")
flags.DEFINE_bool("update", False, "Update an existing agent deployment.")
flags.DEFINE_bool("delete", False, "Delete an existing agent deployment.")
flags.DEFINE_bool("quicktest", False, "Send a quick test message to an existing agent.")
flags.DEFINE_string("message", "What insights can you share today?", "Message to send when running --quicktest.")

flags.mark_bool_flags_as_mutual_exclusive(["create", "update", "delete", "quicktest"])


# -------------------------------------------------------------------
# UTILITIES
# -------------------------------------------------------------------
def _collect_env_vars() -> dict[str, str]:
    """Collect relevant environment variables for remote deployment."""
    env_vars: dict[str, str] = {}

    def _should_include(name: str) -> bool:
        return any(name.startswith(prefix) for prefix in _ENV_PREFIXES) or name in _ENV_PASSTHROUGH

    for key, value in os.environ.items():
        if _should_include(key) and value:
            env_vars[key] = value

    metadata_dir = os.getenv("BQ_AGENT_METADATA_DIR")
    if metadata_dir:
        env_vars.setdefault("BQ_AGENT_METADATA_DIR", metadata_dir)

    return env_vars


def _maybe_print_env_vars(env_vars: dict[str, str]) -> None:
    """Print sanitized environment variables for verification."""
    if not env_vars:
        print("No custom agent environment variables detected; relying on defaults.")
        return

    print("\nConfiguration variables passed to remote agent:")
    for key in sorted(env_vars):
        preview = env_vars[key]
        if len(preview) > 8:
            preview = preview[:4] + "…" + preview[-2:]
        print(f"  - {key}={preview}")


# -------------------------------------------------------------------
# DEPLOYMENT OPERATIONS
# -------------------------------------------------------------------
def create(env_vars: dict[str, str]) -> None:
    """Create a new agent deployment."""
    print("\n=== Creating new Vertex AI agent deployment ===")
    _maybe_print_env_vars(env_vars)

    app = AdkApp(agent=root_agent, enable_tracing=True, env_vars=env_vars)

    remote_agent = agent_engines.create(
        app,
        requirements=str(_PACKAGE_ROOT / "requirements.txt"),
        extra_packages=[str(_PACKAGE_ROOT)],
    )

    print("\n✅ Agent created successfully!")
    print(f"Resource name: {remote_agent.resource_name}\n")


def update(env_vars: dict[str, str], resource_id: str) -> None:
    """Update an existing agent deployment."""
    print("\n=== Updating Vertex AI agent deployment ===")
    _maybe_print_env_vars(env_vars)

    app = AdkApp(agent=root_agent, enable_tracing=True, env_vars=env_vars)

    agent_engines.update(
        resource_name=resource_id,
        agent_engine=app,
        requirements=str(_PACKAGE_ROOT / "requirements.txt"),
        display_name="wmt_bigquery_agent",
        description="British-flavoured Winsights BigQuery agent for wmt-ade-agentspace-dev",
        extra_packages=[str(_PACKAGE_ROOT)],
    )

    print("\n✅ Agent updated successfully!")
    print(f"Resource ID: {resource_id}\n")


def delete(resource_id: str) -> None:
    """Delete an existing agent deployment."""
    print("\n=== Deleting Vertex AI agent deployment ===")
    remote_agent = agent_engines.get(resource_id)
    remote_agent.delete(force=True)
    print(f"✅ Deleted remote agent: {resource_id}\n")


def send_message(resource_id: str, message: str) -> None:
    """Send a message to the deployed agent for testing."""
    print("\n=== Quick test with deployed agent ===")
    remote_agent = agent_engines.get(resource_id)
    session = remote_agent.create_session(user_id="samjad_ae")

    for event in remote_agent.stream_query(
        user_id="samjad_ae",
        session_id=session["id"],
        message=message,
    ):
        print(event)

    print("\n✅ Quick test completed successfully!\n")


# -------------------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------------------
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

    if not project_id:
        print("❌ Missing GOOGLE_CLOUD_PROJECT")
        return
    if not location:
        print("❌ Missing GOOGLE_CLOUD_LOCATION")
        return
    if not bucket:
        print("❌ Missing GOOGLE_CLOUD_STORAGE_BUCKET")
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
            print("❌ --resource_id is required for --update")
            return
        update(env_vars, FLAGS.resource_id)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("❌ --resource_id is required for --delete")
            return
        delete(FLAGS.resource_id)
    elif FLAGS.quicktest:
        if not FLAGS.resource_id:
            print("❌ --resource_id is required for --quicktest")
            return
        send_message(FLAGS.resource_id, FLAGS.message)
    else:
        print("⚠️  No operation specified. Use one of: --create, --update, --delete, --quicktest")


if __name__ == "__main__":
    app.run(main)
