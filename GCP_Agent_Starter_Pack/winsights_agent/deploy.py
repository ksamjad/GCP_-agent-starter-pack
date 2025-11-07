"""Deployment script for Winsights (ADC-enabled)."""

import os
from absl import app, flags
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp
from .Backup.agent import root_agent

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP bucket.")
flags.DEFINE_string("resource_id", None, "ReasoningEngine resource ID.")
flags.DEFINE_bool("create", False, "Creates a new deployment.")
flags.DEFINE_bool("quicktest", False, "Try a new deployment with one turn.")
flags.DEFINE_bool("delete", False, "Deletes an existing deployment.")
flags.DEFINE_bool("update", False, "Updates an existing deployment.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete", "update", "quicktest"])


def create(env_vars: dict[str, str]) -> None:
    """Creates a new deployment."""
    print("🚀 Creating new Vertex Agent Engine deployment...")
    app = AdkApp(
        agent=root_agent,
        enable_tracing=True,
        env_vars=env_vars,
    )
    remote_agent = agent_engines.create(
        app,
        requirements="./requirements.txt",
        extra_packages=["./winsights_agent/agent.py"],
    )
    print(f"✅ Created remote agent: {remote_agent.resource_name}")


def update(env_vars: dict[str, str], resource_id: str) -> None:
    """Updates an existing deployment."""
    print(f"🔄 Updating agent {resource_id} ...")
    app = AdkApp(
        agent=root_agent,
        enable_tracing=True,
        env_vars=env_vars,
    )
    agent_engines.update(
        resource_name=resource_id,
        agent_engine=app,
        requirements="./requirements.txt",
        display_name="Fresh Waste Agent",
        description="Agent generates waste insights",
        extra_packages=["./agent.py"],
    )
    print(f"✅ Updated remote agent: {resource_id}")


def delete(resource_id: str) -> None:
    remote_agent = agent_engines.get(resource_id)
    remote_agent.delete(force=True)
    print(f"🗑️ Deleted remote agent: {resource_id}")


def send_message(resource_id: str, message: str) -> None:
    remote_agent = agent_engines.get(resource_id)
    session = remote_agent.create_session(user_id="traveler0115")
    print(f"💬 Sending message to remote agent {resource_id}")
    for event in remote_agent.stream_query(user_id="traveler0115", session_id=session["id"], message=message):
        print(event)
    print("✅ Done.")


def main(argv: list[str]) -> None:
    load_dotenv()
    env_vars = {
        "CREDENTIALS_TYPE": os.getenv("CREDENTIALS_TYPE", "ADC"),
        "GOOGLE_CLOUD_PROJECT": os.getenv("GOOGLE_CLOUD_PROJECT"),
        "GOOGLE_CLOUD_LOCATION": os.getenv("GOOGLE_CLOUD_LOCATION"),
        "GOOGLE_CLOUD_STORAGE_BUCKET": os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET"),
    }

    project_id = FLAGS.project_id or env_vars["GOOGLE_CLOUD_PROJECT"]
    location = FLAGS.location or env_vars["GOOGLE_CLOUD_LOCATION"]
    bucket = FLAGS.bucket or env_vars["GOOGLE_CLOUD_STORAGE_BUCKET"]

    print(f"PROJECT: {project_id}")
    print(f"LOCATION: {location}")
    print(f"BUCKET: {bucket}")

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=f"gs://{bucket}",
    )

    if FLAGS.create:
        create(env_vars)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("❌ resource_id is required for delete")
            return
        delete(FLAGS.resource_id)
    elif FLAGS.update:
        if not FLAGS.resource_id:
            print("❌ resource_id is required for update")
            return
        update(env_vars, FLAGS.resource_id)
    elif FLAGS.quicktest:
        if not FLAGS.resource_id:
            print("❌ resource_id is required for quicktest")
            return
        send_message(FLAGS.resource_id, "What's up?")
    else:
        print("❌ Unknown command")


if __name__ == "__main__":
    app.run(main)
