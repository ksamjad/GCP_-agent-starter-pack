# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Deployment helper for the SharePoint delegated access agent."""

from __future__ import annotations

import os

from absl import app, flags
from dotenv import load_dotenv
from sharepoint_agent_app.agent import root_agent
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCS staging bucket for build artifacts.")
flags.DEFINE_string("resource_id", None, "Existing Reasoning Engine resource ID.")
flags.DEFINE_bool("create", False, "Create a new deployment.")
flags.DEFINE_bool("update", False, "Update an existing deployment.")
flags.DEFINE_bool("delete", False, "Delete an existing deployment.")
flags.DEFINE_bool("quicktest", False, "Send a single turn to an existing deployment.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "update", "delete", "quicktest"])


def _build_app(env_vars: dict[str, str]) -> AdkApp:
  return AdkApp(
      agent=root_agent,
      enable_tracing=True,
      env_vars=env_vars,
  )


def create(env_vars: dict[str, str]) -> None:
  app_bundle = _build_app(env_vars)
  remote_agent = agent_engines.create(
      app_bundle,
      requirements="./sharepoint_agent_app/requirements.txt",
      extra_packages=["./sharepoint_agent_app/agent.py"],
  )
  print(f"Created remote agent: {remote_agent.resource_name}")


def update(env_vars: dict[str, str], resource_id: str) -> None:
  app_bundle = _build_app(env_vars)
  agent_engines.update(
      resource_name=resource_id,
      agent_engine=app_bundle,
      requirements="./sharepoint_agent_app/requirements.txt",
      display_name=os.getenv("AGENT_DISPLAY_NAME", "SharePoint Research Agent"),
      description="Delegated SharePoint search agent.",
      extra_packages=["./sharepoint_agent_app/agent.py"],
  )
  print(f"Updated remote agent: {resource_id}")


def delete(resource_id: str) -> None:
  remote_agent = agent_engines.get(resource_id)
  remote_agent.delete(force=True)
  print(f"Deleted remote agent: {resource_id}")


def quicktest(resource_id: str) -> None:
  remote_agent = agent_engines.get(resource_id)
  session = remote_agent.create_session(user_id="sharepoint-tester")
  print(f"Streaming response from {resource_id}")
  for event in remote_agent.stream_query(
      user_id="sharepoint-tester",
      session_id=session["id"],
      message="List the most recent policy documents for the Finance site.",
  ):
    print(event)
  print("Done.")


def main(argv: list[str]) -> None:
  del argv
  load_dotenv()

  project_id = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
  location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION")
  bucket = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

  if not project_id:
    raise app.UsageError("Missing GOOGLE_CLOUD_PROJECT or --project_id.")
  if not location:
    raise app.UsageError("Missing GOOGLE_CLOUD_LOCATION or --location.")
  if not bucket:
    raise app.UsageError("Missing GOOGLE_CLOUD_STORAGE_BUCKET or --bucket.")

  vertexai.init(project=project_id, location=location, staging_bucket=f"gs://{bucket}")

  env_vars = {
      "GRAPH_CLIENT_ID": os.getenv("GRAPH_CLIENT_ID", ""),
      "GRAPH_TENANT_ID": os.getenv("GRAPH_TENANT_ID", ""),
      "GRAPH_SCOPES": os.getenv("GRAPH_SCOPES", "Sites.Read.All Files.Read.All"),
      "GRAPH_TOKEN_CACHE": os.getenv("GRAPH_TOKEN_CACHE", ""),
      "GRAPH_HTTP_TIMEOUT": os.getenv("GRAPH_HTTP_TIMEOUT", "30"),
      "AGENT_MODEL": os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
  }

  if FLAGS.create:
    create(env_vars)
  elif FLAGS.update:
    if not FLAGS.resource_id:
      raise app.UsageError("--resource_id is required when updating an agent.")
    update(env_vars, FLAGS.resource_id)
  elif FLAGS.delete:
    if not FLAGS.resource_id:
      raise app.UsageError("--resource_id is required when deleting an agent.")
    delete(FLAGS.resource_id)
  elif FLAGS.quicktest:
    if not FLAGS.resource_id:
      raise app.UsageError("--resource_id is required when quick testing an agent.")
    quicktest(FLAGS.resource_id)
  else:
    raise app.UsageError("Specify one of --create, --update, --delete, or --quicktest.")


if __name__ == "__main__":
  app.run(main)
