#!/usr/bin/env python3
"""
Deploy winsights_agent wheel to Vertex (creates/updates/deletes/quicktests).
"""

import os
from pathlib import Path
from absl import app, flags
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PKG = ROOT / "winsights_agent"

flags = flags
FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID")
flags.DEFINE_string("location", None, "GCP location (default us-central1)")
flags.DEFINE_string("bucket", None, "GCS staging bucket")
flags.DEFINE_string("resource_id", None, "ReasoningEngine resource id")
flags.DEFINE_bool("create", False, "Create")
flags.DEFINE_bool("update", False, "Update")
flags.DEFINE_bool("delete", False, "Delete")
flags.DEFINE_bool("quicktest", False, "Quicktest")
flags.DEFINE_string("message", "What insights can you share today?", "Quicktest message")
flags.mark_bool_flags_as_mutual_exclusive(["create", "update", "delete", "quicktest"])

def _collect_env_vars():
    env = {}
    for k, v in os.environ.items():
        if k.startswith(("BQ_AGENT_", "OAUTH_", "MS_GRAPH_", "GT_WF_")) or k == "GOOGLE_APPLICATION_CREDENTIALS":
            if v:
                env[k] = v
    if "BQ_AGENT_METADATA_DIR" not in env:
        env["BQ_AGENT_METADATA_DIR"] = str(PKG / "metadata")
    return env

def _find_wheel():
    wheels = sorted(DIST.glob("winsights_agent-*.whl"))
    if not wheels:
        raise FileNotFoundError("No wheel in dist/. Run: python build_package.py")
    return wheels[-1]

def create(env_vars):
    wheel = _find_wheel()
    app_obj = AdkApp(agent=__import__("winsights_agent").root_agent, enable_tracing=True, env_vars=env_vars)
    remote = agent_engines.create(app_obj, requirements=str(PKG / "requirements.txt"), extra_packages=[str(wheel)])
    print("Created:", remote.resource_name)

def update(env_vars, resource_id):
    wheel = _find_wheel()
    app_obj = AdkApp(agent=__import__("winsights_agent").root_agent, enable_tracing=True, env_vars=env_vars)
    agent_engines.update(resource_name=resource_id, agent_engine=app_obj, requirements=str(PKG / "requirements.txt"), extra_packages=[str(wheel)])
    print("Updated:", resource_id)

def delete(resource_id):
    a = agent_engines.get(resource_id)
    a.delete(force=True)
    print("Deleted:", resource_id)

def quicktest(resource_id, message):
    a = agent_engines.get(resource_id)
    session = a.create_session(user_id="samjad_ae")
    for e in a.stream_query(user_id="samjad_ae", session_id=session["id"], message=message):
        print(e)

def main(argv):
    load_dotenv()
    env_vars = _collect_env_vars()
    project = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    bucket = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")
    if not all([project, location, bucket]):
        print("Set GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and GOOGLE_CLOUD_STORAGE_BUCKET")
        return
    vertexai.init(project=project, location=location, staging_bucket=f"gs://{bucket}")
    if FLAGS.create:
        create(env_vars)
    elif FLAGS.update:
        if not FLAGS.resource_id:
            print("--resource_id required")
            return
        update(env_vars, FLAGS.resource_id)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("--resource_id required")
            return
        delete(FLAGS.resource_id)
    elif FLAGS.quicktest:
        if not FLAGS.resource_id:
            print("--resource_id required")
            return
        quicktest(FLAGS.resource_id, FLAGS.message)
    else:
        print("No action specified. Use --create/--update/--delete/--quicktest")

if __name__ == "__main__":
    app.run(main)
