"""Deployment helper for the WMT data analyst agent."""

import os
from pathlib import Path
from absl import app, flags
from dotenv import load_dotenv
try:
    from data_analyst_agent_app.agent import root_agent
except ModuleNotFoundError:  # pragma: no cover - fallback for script execution
    from agent import root_agent
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp


_APP_ROOT = Path(__file__).resolve().parent


def _default_extra_packages() -> list[str]:
    """Return the files that must ship with the remote deployment."""

    package_paths: list[Path] = [
        _APP_ROOT / "__init__.py",
        _APP_ROOT / "agent.py",
        _APP_ROOT / "metadata_utils.py",
    ]

    metadata_dir = _APP_ROOT / "metadata"
    if metadata_dir.exists():
        package_paths.append(metadata_dir)

    return [str(path) for path in package_paths if path.exists()]


def _requirements_path() -> str:
    """Return the path to the requirements file for the deployment."""

    requirements_path = _APP_ROOT / "requirements.txt"
    return str(requirements_path)

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


def _resolve_env_vars() -> dict[str, str]:
    """Populate deployment environment variables for the remote agent."""

    env_vars: dict[str, str] = {}
    project_scope = os.getenv("DATA_ANALYST_PROJECT", "wmt-ade-agentspace-dev")
    location = os.getenv("BIGQUERY_LOCATION", "us")
    env_vars["DATA_ANALYST_PROJECT"] = project_scope
    env_vars["BIGQUERY_LOCATION"] = location
    return env_vars


def create(env_vars: dict[str, str]) -> None:
    """Creates a new deployment."""

    app_definition = AdkApp(
        agent=root_agent,
        enable_tracing=True,
        env_vars=env_vars,
    )

    remote_agent = agent_engines.create(
        app_definition,
        requirements=_requirements_path(),
        extra_packages=_default_extra_packages(),
        display_name="WMT Data Analyst Agent",
        description="Metadata-aware analyst with British charm and dashboards.",
    )
    print(f"Created remote agent: {remote_agent.resource_name}")


def update(env_vars: dict[str, str], resource_id: str) -> None:
    """Updates an existing deployment in-place."""

    app_definition = AdkApp(
        agent=root_agent,
        enable_tracing=True,
        env_vars=env_vars,
    )

    agent_engines.update(
        resource_name=resource_id,
        agent_engine=app_definition,
        requirements=_requirements_path(),
        display_name="WMT Data Analyst Agent",
        description="Metadata-aware analyst with British charm and dashboards.",
        extra_packages=_default_extra_packages(),
    )

    print(f"Updated remote agent: {resource_id}")


def delete(resource_id: str) -> None:
    """Deletes a remote deployment."""

    remote_agent = agent_engines.get(resource_id)
    remote_agent.delete(force=True)
    print(f"Deleted remote agent: {resource_id}")


def send_message(resource_id: str, message: str) -> None:
    """Send a message to the deployed agent."""

    remote_agent = agent_engines.get(resource_id)
    session = remote_agent.create_session(
        user_id="data-analyst-user",
    )
    print(f"Trying remote agent: {resource_id}")
    for event in remote_agent.stream_query(
        user_id="data-analyst-user",
        session_id=session["id"],
        message=message,
    ):
        print(event)
    print("Done.")


def main(argv: list[str]) -> None:
    del argv

    load_dotenv()
    env_vars = _resolve_env_vars()

    project_id = (
        FLAGS.project_id if FLAGS.project_id else os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    location = FLAGS.location if FLAGS.location else os.getenv("GOOGLE_CLOUD_LOCATION")
    bucket = FLAGS.bucket if FLAGS.bucket else os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")

    print(f"PROJECT: {project_id}")
    print(f"LOCATION: {location}")
    print(f"BUCKET: {bucket}")

    if not project_id:
        print("Missing required environment variable: GOOGLE_CLOUD_PROJECT")
        return
    if not location:
        print("Missing required environment variable: GOOGLE_CLOUD_LOCATION")
        return
    if not bucket:
        print("Missing required environment variable: GOOGLE_CLOUD_STORAGE_BUCKET")
        return

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=f"gs://{bucket}",
    )

    if FLAGS.create:
        create(env_vars)
    elif FLAGS.delete:
        if not FLAGS.resource_id:
            print("resource_id is required for delete")
            return
        delete(FLAGS.resource_id)
    elif FLAGS.update:
        if not FLAGS.resource_id:
            print("resource_id is required for update")
            return
        update(env_vars, FLAGS.resource_id)
    elif FLAGS.quicktest:
        if not FLAGS.resource_id:
            print("resource_id is required for quicktest")
            return
        send_message(FLAGS.resource_id, "What insights can you surface today?")
    else:
        print("Unknown command")


if __name__ == "__main__":
    app.run(main)
